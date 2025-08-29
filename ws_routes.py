import json, asyncio, threading
from fastapi import WebSocket, WebSocketDisconnect
from stream_analyzer import analyze_stream, active_streams, video_caps

def register_ws_routes(app):
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

                if "stop" in cmd:
                    sid = cmd["stop"]
                    if sid in active_streams:
                        del active_streams[sid]
                        if sid in video_caps:
                            video_caps[sid].release()
                            video_caps.pop(sid, None)

                if cmd.get("stop_all"):
                    for sid in list(active_streams.keys()):
                        del active_streams[sid]
                        if sid in video_caps:
                            video_caps[sid].release()
                            video_caps.pop(sid, None)
                    await websocket.send_json({
                        "type": "status", "status": "all_stopped",
                        "message": "All streams stopped"
                    })

                if "switch" in cmd:
                    switch_data = cmd["switch"]
                    sid, new_url = switch_data["id"], switch_data["url"]

                    if sid in active_streams:
                        del active_streams[sid]
                    if sid in video_caps:
                        video_caps[sid].release()
                        video_caps.pop(sid, None)

                    t = threading.Thread(target=analyze_stream, args=(sid, new_url, websocket, loop), daemon=True)
                    active_streams[sid] = t
                    t.start()

                    await websocket.send_json({
                        "stream_id": sid,
                        "type": "status",
                        "status": "switched",
                        "message": f"Stream {sid} switched to {new_url}"
                    })

        except WebSocketDisconnect:
            for sid in list(active_streams.keys()):
                del active_streams[sid]
                if sid in video_caps:
                    video_caps[sid].release()
                    video_caps.pop(sid, None)
