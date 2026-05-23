"""
Local HTTP API for on-box camera and algorithm control.

Provides endpoints accessible at http://<box_ip>:9100 for operators to
manage which cameras run and which algorithms are applied, independently
of backend commands.
"""
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, Query
from starlette.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from config import ALGORITHM_DIR, BOX_SERIAL, BOX_NAME, LOCAL_API_HOST, LOCAL_API_PORT
from models import AlgorithmConfig, CameraStatus

# These are injected by main.py before the server starts.
camera_manager = None    # type: ignore
runner = None            # type: ignore
rabbitmq = None          # type: ignore

app = FastAPI(title=f"Box {BOX_SERIAL} Local API", version="1.0.0")


# ── request / response models ────────────────────────────────────────

class StartCameraRequest(BaseModel):
    stream_url: str = Field(..., description="RTSP / RTMP / file URL")
    stream_type: str = Field("rtsp", description="Stream type")
    vid_serial: str = Field("", description="Video serial")
    algorithms: list[dict[str, object]] = Field(default_factory=list)

class AlgorithmItem(BaseModel):
    code: str
    params: dict[str, object] = Field(default_factory=dict)


# ── endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "serial": BOX_SERIAL,
        "name": BOX_NAME,
        "status": "running",
        "camera_count": len(camera_manager.cameras) if camera_manager else 0,
    }


@app.get("/cameras")
async def list_cameras():
    """List all cameras and their running status."""
    if camera_manager is None:
        return {"cameras": []}
    return {
        "cameras": [
            {
                "vid_id": s.vid_id,
                "vid_serial": s.vid_serial,
                "stream_url": s.stream_url,
                "status": s.status.value,
                "started_at": s.started_at,
                "algorithms": [{"code": a.code, "params": a.params} for a in s.algorithms],
            }
            for s in camera_manager.cameras.values()
        ]
    }


@app.post("/cameras/{vid_id}/start")
async def start_camera(vid_id: int, req: StartCameraRequest):
    """Start capturing and running algorithms on a camera (local trigger)."""
    if camera_manager is None:
        raise HTTPException(503, "Camera manager not ready")
    algs = [AlgorithmConfig(code=a["code"], params={k: v for k, v in a.items() if k != "code"})
            for a in req.algorithms] if req.algorithms else []

    state = camera_manager.start_camera(
        vid_id=vid_id, stream_url=req.stream_url,
        stream_type=req.stream_type, publish_path=f"publish_{vid_id}",
        algorithms=algs, vid_serial=req.vid_serial,
    )
    if state.status == CameraStatus.ERROR:
        raise HTTPException(500, state.error_message)
    if runner:
        runner.set_algorithms(vid_id, algs)
    return {
        "vid_id": vid_id,
        "status": state.status.value,
        "message": f"Camera {vid_id} {state.status.value}",
    }


@app.post("/cameras/{vid_id}/stop")
async def stop_camera(vid_id: int):
    """Stop a camera (local trigger)."""
    if camera_manager is None:
        raise HTTPException(503, "Camera manager not ready")
    camera_manager.stop_camera(vid_id)
    if runner:
        runner.remove_camera(vid_id)
    return {"vid_id": vid_id, "status": "stopped"}


@app.put("/cameras/{vid_id}/algorithms")
async def update_algorithms(vid_id: int, algorithms: list[AlgorithmItem]):
    """Update algorithms for a running camera."""
    if camera_manager is None or runner is None:
        raise HTTPException(503, "Service not ready")
    algs = [AlgorithmConfig(code=a.code, params=a.params) for a in algorithms]
    state = camera_manager.update_algorithms(vid_id, algs)
    if state is None:
        raise HTTPException(404, f"Camera {vid_id} not found")
    runner.set_algorithms(vid_id, algs)
    return {"vid_id": vid_id, "algorithms": [a.model_dump() for a in algorithms]}


@app.get("/algorithms")
async def list_algorithms():
    """List available algorithm plugins on this box."""
    available = []
    if ALGORITHM_DIR.exists():
        for f in sorted(ALGORITHM_DIR.glob("*.py")):
            if f.stem.startswith("_"):
                continue
            available.append({"code": f.stem, "path": str(f)})
    return {"algorithms": available}


@app.get("/cameras/{vid_id}/status")
async def camera_status(vid_id: int):
    """Get detailed status of a single camera."""
    if camera_manager is None:
        raise HTTPException(503, "Camera manager not ready")
    state = camera_manager.cameras.get(vid_id)
    if state is None:
        raise HTTPException(404, f"Camera {vid_id} not found")
    return {
        "vid_id": state.vid_id,
        "vid_serial": state.vid_serial,
        "status": state.status.value,
        "stream_url": state.stream_url,
        "started_at": state.started_at,
        "error_message": state.error_message,
        "algorithms": [{"code": a.code, "params": a.params} for a in state.algorithms],
    }




@app.get("/cameras/{vid_id}/snapshot")
async def camera_snapshot(vid_id: int):
    """Get a single JPEG frame from a running camera."""
    if camera_manager is None:
        raise HTTPException(503, "Camera manager not ready")
    if vid_id not in camera_manager.cameras:
        raise HTTPException(404, f"Camera {vid_id} not found")
    frame = camera_manager.get_snapshot(vid_id)
    if frame is None:
        raise HTTPException(404, f"Camera {vid_id} has no frame yet")
    ok, jpeg = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(500, "Failed to encode snapshot")
    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


async def generate_camera_stream(vid_id: int):
    import asyncio
    while True:
        frame = camera_manager.get_snapshot(vid_id)
        if frame is not None:
            _, jpeg = cv2.imencode(".jpg", frame)
            data = jpeg.tobytes()
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
        await asyncio.sleep(0.2)


@app.get("/cameras/{vid_id}/stream")
async def camera_stream(vid_id: int):
    """Get an MJPEG stream from a running camera."""
    if camera_manager is None:
        raise HTTPException(503, "Camera manager not ready")
    if vid_id not in camera_manager.cameras:
        raise HTTPException(404, f"Camera {vid_id} not found")
    return StreamingResponse(
        generate_camera_stream(vid_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


def serve(cam_mgr, alg_runner, rmq_client):
    """Start the local API server (blocking). Called from main.py."""
    import uvicorn
    global camera_manager, runner, rabbitmq
    camera_manager = cam_mgr
    runner = alg_runner
    rabbitmq = rmq_client
    uvicorn.run(app, host=LOCAL_API_HOST, port=LOCAL_API_PORT, log_level="info")
