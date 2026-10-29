import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
from app.core.config import API_PORT, ADMIN_USERNAME
from app.core.paths import STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core import access_control
    await asyncio.to_thread(access_control.schema)
    from app.api.study_api import schema as study_schema
    await asyncio.to_thread(study_schema)
    from app.analysis.analysis_schema import ensure_schema
    await asyncio.to_thread(ensure_schema)
    from app.api import health_api
    await asyncio.to_thread(health_api.schema)
    # Preserve the original learning tables; initialize persistent workspace accounts.
    from app.api.ws_handler import frame_queue
    from app.api import ws_handler
    from app.analysis.analyzer import run_analyzer
    from app.analysis import rest_reminder
    # 创建分析结果输出队列，用于推送 learning_status 到设备
    ws_handler.output_queue = asyncio.Queue(maxsize=100)
    broadcast_task = asyncio.create_task(ws_handler._broadcast_results())

    analyzer_task = asyncio.create_task(
        run_analyzer(frame_queue, ws_handler.output_queue)
    )
    reminder_task = asyncio.create_task(rest_reminder.run())
    from app.analysis.maintenance import run as maintain_images
    maintenance_task = asyncio.create_task(maintain_images())

    try:
        yield
    finally:
        from app.analysis.phone_alerts import alerts
        from app.analysis.eye_alerts import alerts as eye_alerts
        from app.analysis.state_sync import screen_sync
        from app.api.camera_bridge import shutdown as stop_camera_bridges
        await stop_camera_bridges()
        tasks = [analyzer_task, broadcast_task, reminder_task, maintenance_task, *list(alerts.tasks), *list(eye_alerts.tasks), *list(screen_sync.tasks)]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)



app = FastAPI(title="小智伴学 · 学生状态监测系统", lifespan=lifespan)

@app.middleware("http")
async def fresh_local_ui(request, call_next):
    ui_request = request.url.path == "/" or request.url.path.startswith("/static/")
    if ui_request:
        # Always return current local assets, not 304 + a previous cached page.
        request.scope["headers"] = [(k,v) for k,v in request.scope["headers"]
                                    if k.lower() not in (b"if-none-match",b"if-modified-since")]
    response = await call_next(request)
    if ui_request:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# 静态文件（管理端页面）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from app.api.ws_handler import router as ws_router
app.include_router(ws_router)

from app.api.api_router import router as api_router
app.include_router(api_router)

from app.api.console_api import router as console_router
app.include_router(console_router)
from app.api.continuous_preview import router as preview_router
app.include_router(preview_router)
from app.api.workspace_api import router as workspace_router
from app.api.network_ingest import router as network_router
app.include_router(workspace_router)
from app.api.study_api import router as study_router
app.include_router(study_router)
from app.api.wellbeing_reports import router as wellbeing_router
app.include_router(wellbeing_router)
from app.api.health_api import router as health_router
app.include_router(health_router)
from app.api.monthly_report import router as report_router
app.include_router(report_router)
app.include_router(network_router)

@app.get("/")
async def root():
    return RedirectResponse("/static/login.html?v=20")




def run():
    """启动服务入口：start.cmd / python main.py 都走这里。"""
    from app.core import site_settings
    from app.core import access_control
    host=site_settings.host()
    if host not in ('127.0.0.1','::1','localhost'):
        access_control.schema()
        if access_control.user(ADMIN_USERNAME)['must_change']:
            raise RuntimeError('请先在本机系统设置中更改默认管理员密码，再启用局域网。')
    site_settings.RUNNING_HOST=host
    uvicorn.run(app,host=host,port=API_PORT,proxy_headers=False,ws_max_size=6*1024*1024)

# Local unified employee portal integration
from app.api.portal_sso import router as portal_sso_router
app.include_router(portal_sso_router)

from app.api.camera_bridge import router as camera_bridge_router
app.include_router(camera_bridge_router)

from app.api.camera_source import router as camera_source_router
app.include_router(camera_source_router)
