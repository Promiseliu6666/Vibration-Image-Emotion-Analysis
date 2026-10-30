import os
import secrets
import json
from app.core import site_settings
from app.core.paths import FRAMES_DIR, PROJECT_ROOT, RUNTIME_DIR
from pathlib import Path

# Local setup lives inside this project. Explicit environment variables win.
_PROJECT_DIR = PROJECT_ROOT
_runtime_config = RUNTIME_DIR / "runtime.json"
if _runtime_config.exists():
    _local = json.loads(_runtime_config.read_text(encoding="utf-8-sig"))
    for _name, _value in {
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": str(_local["mysql_port"]),
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": _local["mysql_password"],
        "MYSQL_DB": _local["mysql_database"],
        "MPLCONFIGDIR": str(RUNTIME_DIR / "cache" / "matplotlib"),
    }.items():
        os.environ.setdefault(_name, _value)


# 服务器
WS_PORT = int(os.getenv("WS_PORT", "8000"))
API_PORT = int(os.getenv("API_PORT", "8000"))

# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "student_monitor")

# JWT
def _jwt_secret():
    configured = os.getenv("JWT_SECRET")
    if configured:
        return configured
    path = RUNTIME_DIR / "jwt-secret.txt"
    path.parent.mkdir(exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32:
        raise RuntimeError("本地登录密钥文件损坏，请检查 .runtime/jwt-secret.txt")
    return value

JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24小时

# 帧处理
FRAME_SAVE_DIR = os.getenv("FRAME_SAVE_DIR", str(FRAMES_DIR))
QUEUE_MAXSIZE = 50

# 每个学习时段最长分钟数，超时自动结束并开启新时段
SESSION_MAX_MINUTES = int(os.getenv("SESSION_MAX_MINUTES", "10"))

# 人离开画面超过此秒数后自动结束当前学习时段，回来后开启新时段
ABSENCE_GRACE_S = int(os.getenv("ABSENCE_GRACE_S", "15"))

# 隐私：是否保存所有帧图片（默认 false，仅保存异常告警帧）
SAVE_ALL_FRAMES = os.getenv("SAVE_ALL_FRAMES", str(site_settings.read()["save_all_frames"])).lower() == "true"

# AES-128 加密密钥（16字节），与小智端固件 crypto_utils.cc 中保持一致
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "xiaozhi-watcher1")

# 数据保留天数，超期自动清理帧图片和数据库记录
FRAME_RETENTION_DAYS = int(os.getenv("FRAME_RETENTION_DAYS", str(site_settings.read()["frame_retention_days"])))

# 初始化管理员账号（首次启动用）
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
