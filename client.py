import asyncio, json, websockets

async def main():
    uri = "ws://localhost:8000/ws/deepface"
    async with websockets.connect(uri, max_size=None) as ws:
        await ws.send(json.dumps({
            "streams": [
                {
                    "id": "localcam",
                    "url": "webcam" # triggers OpenCV to use cv2.VideoCapture(0)
                }
            ]
        }))
        try:
            async for message in ws:
                print("recv:", message)
        except websockets.ConnectionClosedOK:
            print("✅ Webcam stream finished and connection closed cleanly.")
        except websockets.ConnectionClosedError as e:
            print(f"⚠️ Webcam connection closed with error: {e}")

asyncio.run(main())
