from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.env import UploadConfig


def mount_staticfiles(app: FastAPI):
    """
    挂载静态文件
    """
    app.mount(f'{UploadConfig.UPLOAD_PREFIX}', StaticFiles(directory=f'{UploadConfig.UPLOAD_PATH}'), name='profile')

    # 挂载swagger-ui静态文件
    swagger_ui_path = Path(__file__).resolve().parents[1] / 'assets' / 'swagger-ui'
    app.mount('/static/swagger-ui', StaticFiles(directory=swagger_ui_path), name='swagger-ui')
