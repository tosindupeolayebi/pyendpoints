import cv2, json, traceback
from deepface import DeepFace

active_streams = {}
video_caps = {}

def analyze_stream(stream_id, url, websocket, loop):
    try:
        if url == "webcam":
            cap = cv2.VideoCapture(0)
        else:
            cap = cv2.VideoCapture(url)

        video_caps[stream_id] = cap

        while stream_id in active_streams:
            ret, frame = cap.read()
            if not ret:
                print(f"[ERROR] Failed to read frame from {stream_id}")
                break

            try:
                # Run analysis (with enforce_detection=False to avoid crashes on missed faces)
                results = DeepFace.analyze(
                    frame,
                    actions=['gender', 'age', 'emotion'],
                    enforce_detection=False
                )

                # DeepFace returns list sometimes, normalize it
                if isinstance(results, list):
                    results = results[0]

                gender = results.get("gender", "Unknown")
                age = results.get("age", "Unknown")
                dominant_emotion = results.get("dominant_emotion", "Unknown")
                gender_probs = results.get("gender", {})

                payload = {
                    "stream_id": stream_id,
                    "type": "analysis",
                    "gender": gender,
                    "gender_probs": gender_probs,  # 👈 full raw probabilities
                    "age": age,
                    "emotion": dominant_emotion
                }

                # Send over WebSocket
                import asyncio
                asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)

                # Draw overlay on frame for preview
                text = f"{gender} | Age: {age} | Mood: {dominant_emotion}"
                cv2.putText(frame, text, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            except Exception as e:
                print(f"[DeepFace ERROR] {e}")
                traceback.print_exc()

            # Show live feed
            cv2.imshow(f"Live Feed {stream_id}", frame)

            # Exit preview with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        print(f"[INFO] Stream {stream_id} released and window closed")

    except Exception as e:
        print(f"[FATAL ERROR] analyze_stream crashed for {stream_id}: {e}")
        traceback.print_exc()
