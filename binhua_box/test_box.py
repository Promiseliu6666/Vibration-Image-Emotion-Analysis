"""
Algorithm chain test — feed a video file through the real algorithm pipeline
and send results to RabbitMQ to verify end-to-end connectivity.

Usage on the box:
    python3 test_box.py /path/to/video.mp4
    python3 test_box.py /path/to/video.mp4 --no-mq   # skip RabbitMQ, local test only
    python3 test_box.py /path/to/video.mp4 --serve     # also start local API for video proxy
"""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

BOX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BOX_ROOT))

TEST_VID_ID = 9999


def main():
    if len(sys.argv) < 1 or "--help" in sys.argv:
        print(__doc__)
        return

    video_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not video_path or not Path(video_path).exists():
        print(f"Usage: python3 test_box.py <video_file> [--no-mq]")
        print(f"Video not found: {video_path}")
        sys.exit(1)

    use_mq = "--no-mq" not in sys.argv
    serve_api = "--serve" in sys.argv

    # ── Start local API for video proxy (optional) ──
    if serve_api:
        print("[0/5] Starting local API on port 9100...")
        from local_api import app as local_app
        from config import LOCAL_API_HOST, LOCAL_API_PORT
        import uvicorn
        api_thread = threading.Thread(
            target=lambda: uvicorn.run(local_app, host=LOCAL_API_HOST, port=LOCAL_API_PORT, log_level="warning"),
            daemon=True,
        )
        api_thread.start()
        time.sleep(1)
        print(f"       Local API at http://{LOCAL_API_HOST}:{LOCAL_API_PORT} (videos proxy enabled)")

    # ── Load algorithm ──
    print("[1/5] Loading realtime_face_analysis algorithm...")
    from algorithms.realtime_face_analysis import Algorithm as HappinessAlgo
    algo = HappinessAlgo({"confidence": 0.5, "stable_frames_required": 5, "record_duration": 5.0, "face_detect_interval": 5})
    print("       OK (detector DNN + vibraimage CPU)")

    # ── Load face matcher ──
    face_matcher = None
    try:
        from engine.face_matcher import FaceMatcher
        from config import BACKEND_URL
        import httpx
        face_matcher = FaceMatcher(threshold=0.4)
        url = f"{BACKEND_URL}/xuzhou/command/feature_vectors?group_id=1"
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200 and data.get("data"):
                face_matcher.update_gallery(data["data"])
                print(f"       Face gallery: {len(face_matcher.gallery)} people")
    except Exception as e:
        print(f"       Face gallery: unavailable ({e})")

    # ── Run inference on video ──
    print(f"[2/5] Processing: {video_path}")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"       {total} frames @ {fps:.1f} fps")

    all_results = []
    start_time = time.time()
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = algo.infer(frame)
        if result:
            if "image" in result:
                del result["image"]
            result["_frame"] = frame_idx
            result["_time"] = round(frame_idx / fps, 2)
            all_results.append(result)

        frame_idx += 1
        elapsed = time.time() - start_time
        if frame_idx % 50 == 0:
            speed = frame_idx / elapsed if elapsed > 0 else 0
            print(f"       frame {frame_idx}/{total}, speed={speed:.1f} fps, results={len(all_results)}")

    cap.release()
    elapsed = time.time() - start_time
    print(f"       Done: {frame_idx} frames in {elapsed:.1f}s ({frame_idx / elapsed:.1f} fps)")
    print(f"       Results collected: {len(all_results)}")
    print(f"       Video saved: {algo.current_video_path}")

    # ── Filter to only completed analysis ──
    completed_results = [r for r in all_results if r.get("analysis_completed")]
    print(f"\n[3/5] Completed results: {len(completed_results)} / {len(all_results)}")

    # ── Local face matching ──
    for r in completed_results:
        fv = r.get("face_vector")
        if fv and face_matcher and face_matcher.gallery:
            match = face_matcher.match(fv)
            if match:
                r["person_name"] = match["name"]
                r["person_id"] = match["id"]
                r["similarity"] = match["similarity"]
                print(f"       Matched: {match['name']} (sim={match['similarity']:.3f})")
                # strip heavy fields no longer needed
                r.pop("face_vector", None)
                r.pop("face_image", None)
            else:
                r["person_name"] = ""
                print(f"       No match found")
        elif not fv:
            print(f"       No face_vector in result")

    # ── Send to RabbitMQ ──
    if use_mq and completed_results:
        print(f"\n[4/5] Sending {len(completed_results)} results to RabbitMQ...")
        asyncio.run(_send_results(completed_results))
    elif not use_mq:
        print(f"\n[4/5] Skipping RabbitMQ (--no-mq)")

    # ── Device status ──
    if use_mq:
        print(f"[5/5] Publishing device status...")
        asyncio.run(_send_device_status())
        print(f"       Check: GET /xuzhou/command/device_status?vid_id={TEST_VID_ID}")

    print(f"\n{'=' * 55}")
    print(f"Chain test done!")
    print(f"Verify on backend:")
    print(f"  GET /xuzhou/command/device_status?vid_id={TEST_VID_ID}")
    print(f"  GET /analysis/list")
    print(f"{'=' * 55}")


async def _send_results(results: list[dict]) -> None:
    from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD
    from config import RABBITMQ_VHOST, RABBITMQ_EXCHANGE, RABBITMQ_BACKEND_ROUTING_KEY, BOX_SERIAL
    import aio_pika

    try:
        conn = await aio_pika.connect_robust(
            host=RABBITMQ_HOST, port=RABBITMQ_PORT,
            login=RABBITMQ_USER, password=RABBITMQ_PASSWORD,
            virtualhost=RABBITMQ_VHOST, timeout=10,
        )
    except Exception as e:
        print(f"       RabbitMQ connect failed: {e}")
        return

    async with conn:
        channel = await conn.channel()
        exchange = await channel.declare_exchange(RABBITMQ_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)

        # Remove internal keys before sending
        clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]

        # Send in batches
        batch_size = 5
        for i in range(0, len(clean), batch_size):
            batch = clean[i:i + batch_size]
            msg = {
                "key": f"publish_{TEST_VID_ID}",
                "serial": BOX_SERIAL,
                "type": "alarm",
                "data": batch,
            }
            await exchange.publish(
                aio_pika.Message(body=json.dumps(msg).encode(), content_type="application/json"),
                routing_key=RABBITMQ_BACKEND_ROUTING_KEY,
            )
        print(f"       Sent {len(clean)} results in {(len(clean) + batch_size - 1) // batch_size} batches")


async def _send_device_status() -> None:
    from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD
    from config import RABBITMQ_VHOST, RABBITMQ_EXCHANGE, RABBITMQ_BACKEND_ROUTING_KEY, BOX_SERIAL
    import aio_pika

    try:
        conn = await aio_pika.connect_robust(
            host=RABBITMQ_HOST, port=RABBITMQ_PORT,
            login=RABBITMQ_USER, password=RABBITMQ_PASSWORD,
            virtualhost=RABBITMQ_VHOST, timeout=10,
        )
    except Exception:
        return

    async with conn:
        channel = await conn.channel()
        exchange = await channel.declare_exchange(RABBITMQ_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
        msg = {
            "serial": BOX_SERIAL,
            "type": "devices",
            "time": time.time(),
            "devices": [{"vid_id": TEST_VID_ID, "status": "running", "start_time": time.time(), "error_message": ""}],
        }
        await exchange.publish(
            aio_pika.Message(body=json.dumps(msg).encode(), content_type="application/json"),
            routing_key=RABBITMQ_BACKEND_ROUTING_KEY,
        )
        print(f"       Sent device status: vid_id={TEST_VID_ID} running")


if __name__ == "__main__":
    main()
