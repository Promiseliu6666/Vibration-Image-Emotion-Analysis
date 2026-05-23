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

from config import (
    BOX_SERIAL, BOX_NAME, DEVICE_STATUS_INTERVAL,
    ALGORITHM_DIR, MODEL_DIR, WEIGHT_CACHE_DIR,
    LOCAL_API_HOST, LOCAL_API_PORT,
)
from models import CameraTask, CommandAction, InferenceResult
from rabbitmq_client import BoxRabbitMQ, register_command_handler
from camera_manager import CameraManager
from algorithm_runner import AlgorithmRunner
import local_api

# module-level references – set in main_async, read by callbacks / periodic tasks
_camera_manager: CameraManager | None = None
_runner: AlgorithmRunner | None = None
_rabbitmq: BoxRabbitMQ | None = None
_pending_results: dict[str, list[dict]] = {}


async def _handle_backend_command(task: CameraTask, /) -> None:
    assert _camera_manager and _runner
    print(f"[box] received command: vid_id={task.vid_id} action={task.action.value}")
    if task.action in (CommandAction.START, CommandAction.UPDATE):
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
    global _pending_results
    key = f"publish_{result.vid_id}"
    item: dict = {
        "code": result.code,
        "time": (result.time or datetime.now()).isoformat(),
    }
    if result.image_base64:
        item["image"] = result.image_base64
    item.update(result.extra)
    _pending_results.setdefault(key, []).append(item)


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

    asyncio.create_task(_periodic_device_status())
    asyncio.create_task(_periodic_result_flush())

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
