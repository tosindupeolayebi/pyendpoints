import cv2
import json
import time
import asyncio
import threading
import numpy as np
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from deepface import DeepFace

# ----------------- FastAPI App -----------------
app = FastAPI()

# Active stream tracking
active_streams = {}
video_caps = {}

# Global face registry
known_faces = {}   # {face_id: embedding}
next_face_id = 1
lock = threading.Lock()

# Short-term memory for per-stream stability
last_faces = {}  # {stream_id: [ { "face_id": ..., "embedding": ..., "last_seen": ... } ]}

# ----------------- Helpers -----------------

def threadsafe_send(loop, websocket: WebSocket, payload: dict):
    """Send JSON safely from worker thread to WS loop"""
    fut = asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
    try:
        fut.result()
    except Exception:
        pass

def parse_df_result(res):
    """Normalize DeepFace result → (age, gender, emotion, region)."""
    if res is None:
        return None
    item = res[0] if isinstance(res, list) else res
    age = item.get("age")
    gender = item.get("dominant_gender") or item.get("gender")
    emotion = item.get("dominant_emotion") or (
        item.get("emotion") or {}
    ).get("dominant")
    region = item.get("region")
    return age, gender, emotion, region

def get_face_id(embedding, stream_id, threshold=0.6, cache_ttl=5.0):
    """
    Compare embedding to recent cache first, then global registry.
    Returns a stable face_id.
    """
    global next_face_id
    now = time.time()
    emb = np.array(embedding)

    # Initialize per-stream cache if missing
    if stream_id not in last_faces:
        last_faces[stream_id] = []

    # 1. Check recent cache for same stream
    for entry in last_faces[stream_id]:
        dist = np.linalg.norm(emb - np.array(entry["embedding"]))
        if dist < threshold:
            entry["last_seen"] = now
            return entry["face_id"]

    # 2. Cleanup expired entries
    last_faces[stream_id] = [e for e in last_faces[stream_id] if now - e["last_seen"] < cache_ttl]

    # 3. Check global registry
    with lock:
        for fid, stored_embed in known_faces.items():
            dist = np.linalg.norm(emb - np.array(stored_embed))
            if dist < threshold:
                last_faces[stream_id].append({
                    "face_id": fid, "embedding": emb, "last_seen": now
                })
                return fid

        # 4. If no match, assign new global face_id
        fid = f"person_{next_face_id}"
        next_face_id += 1
        known_faces[fid] = emb
        last_faces[stream_id].append({
            "face_id": fid, "embedding": emb, "last_seen": now
        })
        return fid

# ----------------- Stream Analyzer -----------------

def analyze_stream(stream_id: str, url: str, websocket: WebSocket, loop, max_fps=3):
    """Grab frames → DeepFace.analyze + represent → send JSON results."""

    cap = cv2.VideoCapture(0 if url == "webcam" else url)
    video_caps[stream_id] = cap

    if not cap.isOpened():
        threadsafe_send(loop, websocket, {
            "stream_id": stream_id, "type": "error",
            "error": "cannot_open_stream", "url": url,
            "timestamp": datetime.utcnow().isoformat()
        })
        return

    threadsafe_send(loop, websocket, {
        "stream_id": stream_id, "type": "status",
        "status": "started", "message": f"Stream {stream_id} started",
        "timestamp": datetime.utcnow().isoformat()
    })

    min_interval = 1.0 / max_fps
    last_ts = 0.0

    while stream_id in active_streams:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.resize(frame, (640, 480))
        now = time.time()
        if now - last_ts < min_interval:
            if url == "webcam":
                cv2.imshow(f"Live Feed {stream_id}", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            continue
        last_ts = now

        try:
            # Run attribute analysis
            result = DeepFace.analyze(
                frame,
                actions=["age", "gender", "emotion"],
                enforce_detection=False,
                detector_backend="mtcnn"
            )
            parsed = parse_df_result(result)

            if parsed:
                age, gender, emotion, region = parsed

                # Compute embedding
                embedding = DeepFace.represent(
                    frame, model_name="Facenet", enforce_detection=False
                )
                if isinstance(embedding, list):
                    embedding = embedding[0]["embedding"]
                else:
                    embedding = embedding["embedding"]

                face_id = get_face_id(embedding, stream_id)

                # Send JSON result
                threadsafe_send(loop, websocket, {
                    "stream_id": stream_id, "type": "analysis",
                    "results": {
                        "face_id": face_id,
                        "age": int(age) if age else None,
                        "gender": gender,
                        "emotion": emotion,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })

                # Draw preview if webcam
                if url == "webcam" and region:
                    x, y, w, h = region["x"], region["y"], region["w"], region["h"]
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    label = f"{face_id} | {age} | {gender} | {emotion}"
                    cv2.putText(frame, label, (x, y+h+20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            if url == "webcam":
                cv2.imshow(f"Live Feed {stream_id}", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception:
            pass

    cap.release()
    if url == "webcam":
        cv2.destroyAllWindows()

    threadsafe_send(loop, websocket, {
        "stream_id": stream_id, "type": "status",
        "status": "stopped", "message": f"Stream {stream_id} stopped",
        "timestamp": datetime.utcnow().isoformat()
    })

# ----------------- WebSocket Endpoint -----------------

@app.websocket("/ws/deepface")
async def ws_deepface(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        data = await websocket.receive_json()
        streams = data.get("streams", [])
        for st in streams:
            sid, url = st["id"], st["url"]
            t = threading.Thread(target=analyze_stream, args=(sid, url, websocket, loop), daemon=True)
            active_streams[sid] = t
            t.start()

        while True:
            msg = await websocket.receive_text()
            try:
                cmd = json.loads(msg)
            except json.JSONDecodeError:
                continue

            # ---- Stop a specific stream ----
            if "stop" in cmd:
                sid = cmd["stop"]
                if sid in active_streams:
                    del active_streams[sid]
                    if sid in video_caps:
                        video_caps[sid].release()
                        video_caps.pop(sid, None)

            # ---- Stop all streams ----
            if cmd.get("stop_all"):
                for sid in list(active_streams.keys()):
                    del active_streams[sid]
                    if sid in video_caps:
                        video_caps[sid].release()
                        video_caps.pop(sid, None)
                await websocket.send_json({
                    "type": "status", "status": "all_stopped",
                    "message": "All streams stopped",
                    "timestamp": datetime.utcnow().isoformat()
                })

            # ---- Switch stream URL ----
            if "switch" in cmd:
                switch_data = cmd["switch"]
                sid, new_url = switch_data["id"], switch_data["url"]

                # Stop old stream
                if sid in active_streams:
                    del active_streams[sid]
                if sid in video_caps:
                    video_caps[sid].release()
                    video_caps.pop(sid, None)

                # Start new stream with same stream_id
                t = threading.Thread(target=analyze_stream, args=(sid, new_url, websocket, loop), daemon=True)
                active_streams[sid] = t
                t.start()

                await websocket.send_json({
                    "stream_id": sid,
                    "type": "status",
                    "status": "switched",
                    "message": f"Stream {sid} switched to {new_url}",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        for sid in list(active_streams.keys()):
            del active_streams[sid]
            if sid in video_caps:
                video_caps[sid].release()
                video_caps.pop(sid, None)
