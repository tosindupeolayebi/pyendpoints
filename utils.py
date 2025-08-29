import asyncio

def threadsafe_send(loop, websocket, payload: dict):
    """Send JSON safely from worker thread to WS loop."""
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
    emotion = item.get("dominant_emotion") or (item.get("emotion") or {}).get("dominant")
    region = item.get("region")
    return age, gender, emotion, region
