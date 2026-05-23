"""
RabbitMQ client for the box – bidirectional communication with the backend.

  Box → Backend  (publish):  device status + alarm/inference results
  Backend → Box  (consume):  start / stop / update camera commands
"""
import asyncio
import json
import time
from collections.abc import Callable, Awaitable

import aio_pika

from config import (
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD,
    RABBITMQ_VHOST, RABBITMQ_EXCHANGE,
    RABBITMQ_BOX_ROUTING_KEY, RABBITMQ_BACKEND_ROUTING_KEY,
    BOX_SERIAL, BOX_NAME, RECONNECT_DELAY, BOX_PUBLIC_HOST, BOX_PUBLIC_PORT,
)
from models import CameraTask, CommandAction, AlgorithmConfig

CommandCallback = Callable[[CameraTask], Awaitable[None]]

command_handlers: list[CommandCallback] = []


def register_command_handler(handler: CommandCallback) -> None:
    command_handlers.append(handler)


def _parse_camera_task(raw: dict) -> CameraTask | None:
    """Parse a backend command message into a CameraTask. Returns None if invalid."""
    try:
        vid_id = raw.get("vid_id")
        if vid_id is None:
            return None
        algorithms = []
        for alg in raw.get("algorithms") or []:
            algorithms.append(AlgorithmConfig(
                code=alg.get("code", ""),
                params={k: v for k, v in alg.items() if k != "code"},
            ))
        return CameraTask(
            vid_id=int(vid_id),
            vid_serial=raw.get("vid_serial", ""),
            action=CommandAction(raw.get("action", "start")),
            stream_url=raw.get("stream_url", ""),
            stream_type=raw.get("stream_type", "rtsp"),
            algorithms=algorithms,
            publish_path=raw.get("publish_path", f"publish_{vid_id}"),
        )
    except (ValueError, TypeError, KeyError):
        return None


async def _message_handler(message: aio_pika.IncomingMessage) -> None:
    """Handle incoming RabbitMQ messages (backend commands)."""
    async with message.process():
        try:
            body = json.loads(message.body.decode())
        except json.JSONDecodeError:
            return
        task = _parse_camera_task(body)
        if task is None:
            return
        for handler in command_handlers:
            await handler(task)


class BoxRabbitMQ:
    """Manages the box's RabbitMQ connection and message publishing."""

    def __init__(self):
        self._connection: aio_pika.Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self._connection is not None and not self._connection.is_closed:
                return
            self._connection = await aio_pika.connect_robust(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                login=RABBITMQ_USER, password=RABBITMQ_PASSWORD,
                virtualhost=RABBITMQ_VHOST,
                reconnect_interval=RECONNECT_DELAY,
            )
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                RABBITMQ_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True,
            )

    async def start_consuming(self) -> None:
        await self.connect()
        queue = await self._channel.declare_queue(
            f"box_{RABBITMQ_BOX_ROUTING_KEY}", durable=True,
        )
        await queue.bind(self._exchange, routing_key=RABBITMQ_BOX_ROUTING_KEY)
        await queue.consume(_message_handler)

    async def publish(self, routing_key: str, body: dict | str) -> None:
        await self.connect()
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False, default=str)
        await self._exchange.publish(
            aio_pika.Message(body=body.encode()),
            routing_key=routing_key,
        )

    async def publish_device_status(self, devices: list[dict]) -> None:
        await self.publish(RABBITMQ_BACKEND_ROUTING_KEY, {
            "serial": BOX_SERIAL,
            "type": "devices",
            "time": time.time(),
            "devices": devices,
        })

    async def publish_alarm(self, key: str, data: list[dict]) -> None:
        await self.publish(RABBITMQ_BACKEND_ROUTING_KEY, {
            "key": key,
            "serial": BOX_SERIAL,
            "type": "alarm",
            "data": data,
        })

    async def publish_box_register(self, capabilities: list[str] | None = None) -> None:
        """Send box online registration / heartbeat to backend."""
        import socket
        hostname = socket.gethostname()
        ip = BOX_PUBLIC_HOST
        if not ip:
            try:
                ip = socket.gethostbyname(hostname)
            except Exception:
                ip = hostname
        await self.publish(RABBITMQ_BACKEND_ROUTING_KEY, {
            "serial": BOX_SERIAL,
            "type": "box_register",
            "time": time.time(),
            "box_name": BOX_NAME,
            "host": hostname,
            "ip": ip,
            "port": BOX_PUBLIC_PORT,
            "capabilities": capabilities or [],
        })

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
