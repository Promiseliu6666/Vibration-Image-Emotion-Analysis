"""
Box RabbitMQ connectivity test – upload to box and run.

Usage:
    python3 test_rabbitmq.py                          # try common credentials
    python3 test_rabbitmq.py --host 192.168.31.249    # custom host
    python3 test_rabbitmq.py --user admin --pass xxx  # custom credentials
"""
import asyncio
import argparse

CREDENTIALS = [
    ("guest", "guest"),
    ("hhx", "hhx4201!"),
    ("admin", "admin"),
]

async def try_connect(host: str, port: int, user: str, pwd: str, vhost: str = "/") -> bool:
    import aio_pika
    url = f"amqp://{user}:{pwd}@{host}:{port}/{vhost.lstrip('/')}"
    try:
        c = await aio_pika.connect_robust(url, timeout=5)
        print(f"  ✓ 连接成功")
        await c.close()
        return True
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test RabbitMQ connection")
    parser.add_argument("--host", default="192.168.31.249")
    parser.add_argument("--port", type=int, default=5672)
    parser.add_argument("--user")
    parser.add_argument("--pass", dest="pwd")
    args = parser.parse_args()

    print(f"目标: {args.host}:{args.port}")
    print()

    if args.user:
        await try_connect(args.host, args.port, args.user, args.pwd or "")
    else:
        print("自动尝试常用凭证...")
        for user, pwd in CREDENTIALS:
            print(f"  {user}:{pwd}", end="")
            if await try_connect(args.host, args.port, user, pwd):
                print(f"\n  → 盒子启动命令:")
                print(f"    RABBITMQ_HOST={args.host} RABBITMQ_USER={user} RABBITMQ_PASSWORD={pwd} python3 main.py")
                return


if __name__ == "__main__":
    asyncio.run(main())
