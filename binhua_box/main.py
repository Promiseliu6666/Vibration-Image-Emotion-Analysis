"""
Box service entrypoint – wires together RabbitMQ communication, camera
management, algorithm execution, and the local HTTP API.

Usage:
    python -m box.main
"""
import asyncio
import signal
import sys
import threading
from datetime import datetime

import httpx

from config import (
    BOX_SERIAL, BOX_NAME, DEVICE_STATUS_INTERVAL,
    ALGORITHM_DIR, MODEL_DIR, WEIGHT_CACHE_DIR,
    LOCAL_API_HOST, LOCAL_API_PORT, BACKEND_URL,
)
from models import AlgorithmConfig, CameraTask, CommandAction, InferenceResult
from rabbitmq_client import BoxRabbitMQ, register_command_handler
from camera_manager import CameraManager
from algorithm_runner import AlgorithmRunner
from engine.face_matcher import FaceMatcher
import local_api

# module-level references – set in main_async, read by callbacks / periodic tasks
_camera_manager: CameraManager | None = None
_runner: AlgorithmRunner | None = None
_rabbitmq: BoxRabbitMQ | None = None
_pending_results: dict[str, list[dict]] = {}
_face_matcher: FaceMatcher = FaceMatcher(threshold=0.4)


async def _fetch_gallery() -> bool:
    """Fetch face feature vectors from backend server. Returns True on success."""
    url = f"{BACKEND_URL}/xuzhou/command/feature_vectors?group_id=1"
    import asyncio as aio
    try:
        resp = await aio.to_thread(httpx.get, url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200 and data.get("data"):
                _face_matcher.update_gallery(data["data"])
                print(f"[box] face gallery synced: {len(_face_matcher.gallery)} people")
                return True
    except Exception as e:
        print(f"[box] face gallery fetch failed: {e}")
    return False


async def _periodic_gallery_refresh() -> None:
    """Refresh face gallery every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        await _fetch_gallery()


async def _handle_backend_command(task: CameraTask, /) -> None:
    assert _camera_manager and _runner
    print(f"[box] received command: vid_id={task.vid_id} action={task.action.value}")
    if task.action in (CommandAction.START, CommandAction.UPDATE):
        for alg in task.algorithms:
            alg.params.setdefault("stream_url", task.stream_url)
            alg.params.setdefault("stream_type", task.stream_type)
        _camera_manager.start_camera(
            vid_id=task.vid_id, stream_url=task.stream_url,
            stream_type=task.stream_type, publish_path=task.publish_path,
            algorithms=task.algorithms, vid_serial=task.vid_serial,
        )
        _runner.set_algorithms(task.vid_id, task.algorithms)
    elif task.action == CommandAction.STOP:
        _camera_manager.stop_camera(task.vid_id)
        _runner.remove_camera(task.vid_id)

    # 立即回传设备状态，不等定时器
    if _rabbitmq:
        try:
            await _rabbitmq.publish_device_status(_camera_manager.get_device_status_list())
        except Exception:
            pass


def _on_algorithm_result(result: InferenceResult) -> None:
    print(f"[DEBUG] main: result vid={result.vid_id} code={result.code} extra_keys={list(result.extra.keys()) if isinstance(result.extra, dict) else 'scalar'} has_image={result.image_base64 is not None}", flush=True)
    global _pending_results
    key = f"publish_{result.vid_id}"
    item: dict = {
        "code": result.code,
        "time": (result.time or datetime.now()).isoformat(),
    }
    if result.image_base64:
        item["image"] = result.image_base64
    item.update(result.extra)

    # local face match — only on completed analysis
    if item.get("analysis_completed"):
        face_vector = item.get("face_vector")
        print(f"[DEBUG] main: face match gallery_size={len(_face_matcher.gallery)} has_vector={face_vector is not None}", flush=True)
        if face_vector and _face_matcher.gallery:
            match = _face_matcher.match(face_vector)
            if match:
                item["person_name"] = match["name"]
                item["person_id"] = match["id"]
                item["similarity"] = match["similarity"]
                print(f"[DEBUG] main: face matched name={match['name']} similarity={match['similarity']}", flush=True)
                # matched locally — strip heavy fields the server no longer needs
                item.pop("face_vector", None)
                item.pop("face_image", None)
            else:
                print(f"[DEBUG] main: face no match (gallery has {len(_face_matcher.gallery)} people), keeping vector for server", flush=True)
        elif not _face_matcher.gallery:
            # gallery unavailable, keep face_vector for server fallback
            print(f"[DEBUG] main: face match skipped — gallery empty, keeping vector for server", flush=True)
        else:
            print(f"[DEBUG] main: face match skipped — no face_vector in result", flush=True)

    _pending_results.setdefault(key, []).append(item)


async def _auto_start_cameras() -> None:
    """Fetch cameras bound to this box from backend and auto-start them."""
    url = f"{BACKEND_URL}/xuzhou/command/box_cameras?box_serial={BOX_SERIAL}"
    import asyncio as aio
    try:
        resp = await aio.to_thread(httpx.get, url, timeout=10)
        if resp.status_code != 200:
            print(f"[box] auto-start: backend returned {resp.status_code}")
            return
        data = resp.json()
        cameras = data.get("data", []) if data.get("code") == 200 else []
    except Exception as e:
        print(f"[box] auto-start: failed to fetch cameras ({e})")
        return

    if not cameras:
        print("[box] auto-start: no cameras bound to this box")
        return

    assert _camera_manager and _runner
    started = 0
    for cam in cameras:
        vid_id = cam.get("vid_id")
        algs = [AlgorithmConfig(code=a["code"], params={k: v for k, v in a.items() if k != "code"})
                for a in cam.get("algorithms", [])]
        if not algs:
            continue
        for alg in algs:
            alg.params.setdefault("stream_url", cam.get("stream_url", ""))
            alg.params.setdefault("stream_type", cam.get("stream_type", "rtsp"))
        _camera_manager.start_camera(
            vid_id=vid_id, stream_url=cam.get("stream_url", ""),
            stream_type=cam.get("stream_type", "rtsp"),
            publish_path=f"publish_{vid_id}",
            algorithms=algs, vid_serial=cam.get("vid_serial", ""),
        )
        _runner.set_algorithms(vid_id, algs)
        started += 1
        print(f"[box] auto-start: vid_id={vid_id} ({cam.get('vid_name', '')}) with {[a.code for a in algs]}")

    if started and _rabbitmq:
        try:
            await _rabbitmq.publish_device_status(_camera_manager.get_device_status_list())
        except Exception:
            pass
    print(f"[box] auto-start: {started} camera(s) started")


async def _periodic_device_status() -> None:
    assert _rabbitmq and _camera_manager
    while True:
        await asyncio.sleep(DEVICE_STATUS_INTERVAL)
        try:
            devices = _camera_manager.get_device_status_list()
            if devices:
                await _rabbitmq.publish_device_status(devices)
        except Exception:
            pass


async def _periodic_result_flush() -> None:
    global _pending_results
    assert _rabbitmq
    while True:
        await asyncio.sleep(1.0)
        if not _pending_results:
            continue
        batch = _pending_results
        _pending_results = {}
        for key, data in batch.items():
            try:
                await _rabbitmq.publish_alarm(key, data)
            except Exception:
                pass


def _ensure_dirs() -> None:
    for d in (ALGORITHM_DIR, MODEL_DIR, WEIGHT_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


async def main_async() -> None:
    global _camera_manager, _runner, _rabbitmq

    _ensure_dirs()

    _camera_manager = CameraManager()
    _runner = AlgorithmRunner()

    _camera_manager.on_frame(
        lambda vid_id, frame, algs: _runner.process_frame(vid_id, frame)
    )
    _runner.on_result(_on_algorithm_result)
    register_command_handler(_handle_backend_command)

    _rabbitmq = BoxRabbitMQ()
    await _rabbitmq.connect()
    await _rabbitmq.start_consuming()

    # wire module globals so the local API can access the running components
    local_api.camera_manager = _camera_manager
    local_api.runner = _runner
    local_api.rabbitmq = _rabbitmq

    # start local HTTP API in background thread
    _api_thread = threading.Thread(
        target=local_api.serve, args=(_camera_manager, _runner, _rabbitmq),
        daemon=True,
    )
    _api_thread.start()

    # scan and register available algorithms
    _capabilities = [f.stem for f in ALGORITHM_DIR.glob("*.py") if not f.stem.startswith("_")]
    await _rabbitmq.publish_box_register(_capabilities)

    print(f"[box] {BOX_NAME} (serial={BOX_SERIAL}) connected to RabbitMQ")
    print(f"[box] listening on routing key: algorithm_{BOX_SERIAL}")
    print(f"[box] capabilities: {_capabilities}")
    print(f"[box] local API at http://{LOCAL_API_HOST}:{LOCAL_API_PORT}")

    # initial gallery fetch
    await _fetch_gallery()

    # auto-start cameras bound to this box
    await _auto_start_cameras()

    asyncio.create_task(_periodic_device_status())
    asyncio.create_task(_periodic_result_flush())
    asyncio.create_task(_periodic_gallery_refresh())

    async def _periodic_heartbeat() -> None:
        assert _rabbitmq
        while True:
            await asyncio.sleep(30)  # every 30 seconds
            try:
                _capabilities = [f.stem for f in ALGORITHM_DIR.glob("*.py") if not f.stem.startswith("_")]
                await _rabbitmq.publish_box_register(_capabilities)
            except Exception:
                pass

    asyncio.create_task(_periodic_heartbeat())

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await stop_event.wait()
    print("[box] shutting down...")
    _camera_manager.stop_all()
    await _rabbitmq.close()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
