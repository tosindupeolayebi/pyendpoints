import cv2, time, threading
from datetime import datetime
from deepface import DeepFace
from utils import threadsafe_send, parse_df_result
from face_registry import get_face_id

active_streams = {}
video_caps = {}

def analyze_stream(stream_id: str, url: str, websocket, loop, max_fps=3):
    """Grab frames → DeepFace.analyze → send JSON results."""
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
            result = DeepFace.analyze(frame, actions=["age", "gender", "emotion"],
                                      enforce_detection=False, detector_backend="retinaface")
            parsed = parse_df_result(result)
            if parsed:
                age, gender, emotion, region = parsed
                embedding = DeepFace.represent(frame, model_name="Facenet", enforce_detection=False)
                if isinstance(embedding, list):
                    embedding = embedding[0]["embedding"]
                else:
                    embedding = embedding["embedding"]

                face_id = get_face_id(embedding, stream_id)

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



# import cv2
# import time
# import threading
# import traceback
# from datetime import datetime
# from deepface import DeepFace
# from utils import threadsafe_send, parse_df_result
# from face_registry import get_face_id

# active_streams = {}
# video_caps = {}

# def analyze_stream(stream_id, url, websocket, loop, max_fps=3):
#     """Grab frames → DeepFace.analyze → send JSON results."""
#     try:
#         # Initialize video capture
#         cap = cv2.VideoCapture(0 if url == "webcam" else url)
#         if not cap.isOpened():
#             print(f"[ERROR] Cannot open stream {stream_id} at {url}")
#             threadsafe_send(loop, websocket, {
#                 "stream_id": stream_id,
#                 "type": "error",
#                 "error": "cannot_open_stream",
#                 "url": url,
#                 "timestamp": datetime.utcnow().isoformat()
#             })
#             return

#         video_caps[stream_id] = cap
#         print(f"[INFO] Stream {stream_id} started for {url}")

#         # Send start status
#         threadsafe_send(loop, websocket, {
#             "stream_id": stream_id,
#             "type": "status",
#             "status": "started",
#             "message": f"Stream {stream_id} started",
#             "timestamp": datetime.utcnow().isoformat()
#         })

#         # Frame rate control
#         min_interval = 1.0 / max_fps
#         last_ts = 0.0

#         while stream_id in active_streams:
#             ret, frame = cap.read()
#             if not ret:
#                 print(f"[ERROR] Failed to read frame from {stream_id}")
#                 break

#             # Resize frame to reduce processing load
#             frame = cv2.resize(frame, (640, 480))

#             # Enforce frame rate limit
#             now = time.time()
#             if now - last_ts < min_interval:
#                 if url == "webcam":
#                     cv2.imshow(f"Live Feed {stream_id}", frame)
#                     if cv2.waitKey(1) & 0xFF == ord('q'):
#                         break
#                 continue
#             last_ts = now

#             try:
#                 # Analyze frame with DeepFace
#                 result = DeepFace.analyze(
#                     frame,
#                     actions=["age", "gender", "emotion"],
#                     enforce_detection=False,
#                     detector_backend="retinaface"  # Reverted to retinaface for consistency
#                 )
#                 parsed = parse_df_result(result)
#                 if parsed:
#                     age, gender, emotion, region = parsed
#                     embedding = DeepFace.represent(
#                         frame,
#                         model_name="Facenet",
#                         enforce_detection=False
#                     )
#                     if isinstance(embedding, list):
#                         embedding = embedding[0]["embedding"]
#                     else:
#                         embedding = embedding["embedding"]

#                     face_id = get_face_id(embedding, stream_id)

#                     # Send analysis results
#                     payload = {
#                         "stream_id": stream_id,
#                         "type": "analysis",
#                         "results": {
#                             "face_id": face_id,
#                             "age": int(age) if age else None,
#                             "gender": gender,
#                             "emotion": emotion,
#                             "timestamp": datetime.utcnow().isoformat()
#                         }
#                     }
#                     threadsafe_send(loop, websocket, payload)

#                     # Draw overlay for webcam preview
#                     if url == "webcam" and region:
#                         x, y, w, h = region["x"], region["y"], region["w"], region["h"]
#                         cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
#                         label = f"{face_id} | {age} | {gender} | {emotion}"
#                         cv2.putText(
#                             frame,
#                             label,
#                             (x, y+h+20),
#                             cv2.FONT_HERSHEY_SIMPLEX,
#                             0.6,
#                             (0, 255, 0),
#                             2
#                         )

#             except Exception as e:
#                 print(f"[DeepFace ERROR] Stream {stream_id}: {e}")
#                 traceback.print_exc()
#                 continue  # Continue to next frame instead of breaking

#             # Show live feed for webcam
#             if url == "webcam":
#                 cv2.imshow(f"Live Feed {stream_id}", frame)
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     break

#     except Exception as e:
#         print(f"[FATAL ERROR] analyze_stream crashed for {stream_id}: {e}")
#         traceback.print_exc()

#     finally:
#         # Clean up resources
#         if stream_id in video_caps:
#             video_caps[stream_id].release()
#             video_caps.pop(stream_id, None)
#         if url == "webcam":
#             cv2.destroyWindow(f"Live Feed {stream_id}")
#         print(f"[INFO] Stream {stream_id} released and window closed")
#         threadsafe_send(loop, websocket, {
#             "stream_id": stream_id,
#             "type": "status",
#             "status": "stopped",
#             "message": f"Stream {stream_id} stopped",
#             "timestamp": datetime.utcnow().isoformat()
#         })