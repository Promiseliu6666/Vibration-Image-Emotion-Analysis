"""
Box configuration – RabbitMQ connection, box identity, local API server, and runtime paths.
"""
import os
from pathlib import Path

BOX_ROOT = Path(__file__).resolve().parent

# ── Box identity ──────────────────────────────────────────────────────────
BOX_SERIAL = os.environ.get("BOX_SERIAL", "0004")
BOX_NAME = os.environ.get("BOX_NAME", f"box_{BOX_SERIAL}")

# ── RabbitMQ ──────────────────────────────────────────────────────────────
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "192.168.0.246")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "hhx")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "hhx4201!")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")
RABBITMQ_EXCHANGE = os.environ.get("RABBITMQ_EXCHANGE", "xuzhou")

# routing key the box LISTENS on for backend commands
RABBITMQ_BOX_ROUTING_KEY = os.environ.get("RABBITMQ_BOX_ROUTING_KEY", f"algorithm_{BOX_SERIAL}")
# routing key the backend listens on – the box PUBLISHES results here
RABBITMQ_BACKEND_ROUTING_KEY = os.environ.get("RABBITMQ_BACKEND_ROUTING_KEY", "api_service")

# ── Local HTTP API ────────────────────────────────────────────────────────
LOCAL_API_HOST = os.environ.get("LOCAL_API_HOST", "0.0.0.0")
LOCAL_API_PORT = int(os.environ.get("LOCAL_API_PORT", "9100"))
BOX_PUBLIC_HOST = os.environ.get("BOX_PUBLIC_HOST", "")
BOX_PUBLIC_PORT = int(os.environ.get("BOX_PUBLIC_PORT", str(LOCAL_API_PORT)))

# ── Algorithm / model paths ───────────────────────────────────────────────
ALGORITHM_DIR = Path(os.environ.get("ALGORITHM_DIR", BOX_ROOT / "algorithms"))
MODEL_DIR = Path(os.environ.get("MODEL_DIR", BOX_ROOT / "models"))
WEIGHT_CACHE_DIR = Path(os.environ.get("WEIGHT_CACHE_DIR", BOX_ROOT / "weights"))

# ── Backend server (for fetching gallery, etc.) ────────────────────────────
BACKEND_URL = os.environ.get("BACKEND_URL", "http://192.168.0.246:9099")

# ── Runtime limits ────────────────────────────────────────────────────────
MAX_CONCURRENT_CAMERAS = int(os.environ.get("MAX_CONCURRENT_CAMERAS", "8"))
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "5"))  # seconds
DEVICE_STATUS_INTERVAL = int(os.environ.get("DEVICE_STATUS_INTERVAL", "3"))  # seconds
RECONNECT_DELAY = int(os.environ.get("RECONNECT_DELAY", "5"))  # seconds
