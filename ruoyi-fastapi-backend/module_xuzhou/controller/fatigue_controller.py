"""HTTP proxy from the platform backend to the local fatigue model service."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from hik_vision.camera_contract import resolve_camera_selection
from hik_vision.hik_vision import _require_video_stream_user, _require_video_user

fatigue_controller = APIRouter(prefix="/fatigue", tags=["疲劳检测"])

FATIGUE_SERVICE_URL = os.getenv(
    "FATIGUE_SERVICE_URL",
    "http://127.0.0.1:9101",
).rstrip("/")


async def _forward(path: str, params: dict[str, str]) -> Response:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=35.0) as client:
            upstream = await client.request(
                "GET",
                f"{FATIGUE_SERVICE_URL}{path}",
                params=params,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail="疲劳检测服务未启动，请检查 fatigue-service 进程",
        ) from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


def _camera_params(
    camera_id: str,
    source: str,
    device_id: str,
) -> dict[str, str]:
    try:
        selection = resolve_camera_selection(camera_id, source, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return selection.legacy_params()


@fatigue_controller.get("/status", dependencies=[Depends(_require_video_user)])
async def get_fatigue_status() -> Response:
    return await _forward("/health", {})


@fatigue_controller.get("/results", dependencies=[Depends(_require_video_user)])
async def get_fatigue_results(
    camera_id: str = Query(default=""),
    source: str = Query(default="local"),
    device_id: str = Query(default=""),
) -> Response:
    return await _forward(
        "/results",
        _camera_params(camera_id, source, device_id),
    )


@fatigue_controller.get("/feed", dependencies=[Depends(_require_video_stream_user)])
async def get_fatigue_feed(
    camera_id: str = Query(default=""),
    source: str = Query(default="local"),
    device_id: str = Query(default=""),
    show_boxes: int = Query(default=0, ge=0, le=1),
) -> Response:
    camera_params = _camera_params(camera_id, source, device_id)
    client = httpx.AsyncClient(trust_env=False, timeout=None)
    request = client.build_request(
        "GET",
        f"{FATIGUE_SERVICE_URL}/feed",
        params={
            **camera_params,
            "show_boxes": str(show_boxes),
        },
    )
    try:
        upstream = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=503,
            detail="疲劳检测视频服务未启动，请检查 fatigue-service 进程",
        ) from exc

    if upstream.status_code != 200:
        content = await upstream.aread()
        media_type = upstream.headers.get(
            "content-type",
            "application/json",
        ).split(";", 1)[0]
        await upstream.aclose()
        await client.aclose()
        return Response(
            content=content,
            status_code=upstream.status_code,
            media_type=media_type,
        )

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        media_type=upstream.headers.get(
            "content-type",
            "multipart/x-mixed-replace; boundary=frame",
        ),
        headers={"Cache-Control": "no-store, no-cache"},
    )


@fatigue_controller.post("/reset", dependencies=[Depends(_require_video_user)])
async def reset_fatigue_results(
    camera_id: str = Query(default=""),
    source: str = Query(default="local"),
    device_id: str = Query(default=""),
) -> Response:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=35.0) as client:
            upstream = await client.post(
                f"{FATIGUE_SERVICE_URL}/reset",
                params=_camera_params(camera_id, source, device_id),
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail="疲劳检测服务未启动，请检查 fatigue-service 进程",
        ) from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
