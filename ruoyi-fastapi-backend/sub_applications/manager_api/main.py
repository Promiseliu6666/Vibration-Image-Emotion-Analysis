from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sub_applications.manager_api.api.health import router as health_router
from sub_applications.manager_api.api.ruoyi import router as ruoyi_router
from sub_applications.manager_api.api.xiaozhi import router as xiaozhi_router
from sub_applications.manager_api.bootstrap import init_database
from sub_applications.manager_api.core.config import Settings, get_settings


def _install_cors(app: FastAPI, settings: Settings) -> None:
    allow_all = "*" in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_embedded_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(
        title=config.app_name,
        version="1.0.0",
        docs_url="/doc.html",
        openapi_url="/v3/api-docs",
    )
    _install_cors(app, config)

    @app.on_event("startup")
    def _startup() -> None:
        init_database()

    app.include_router(health_router)

    if config.ruoyi_api_prefix:
        app.include_router(ruoyi_router, prefix=config.ruoyi_api_prefix)
    else:
        app.include_router(ruoyi_router)

    app.include_router(xiaozhi_router, prefix=config.app_mount_path)
    return app


def mount_manager_api(parent_app: FastAPI, prefix: str | None = None) -> None:
    config = get_settings()
    mount_prefix = prefix or config.manager_api_mount_prefix
    parent_app.mount(mount_prefix, create_embedded_app(config))


def create_app() -> FastAPI:
    return create_embedded_app(get_settings())
