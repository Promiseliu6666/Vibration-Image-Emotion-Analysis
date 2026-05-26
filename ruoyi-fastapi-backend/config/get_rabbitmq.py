import aio_pika
from aio_pika.exceptions import AMQPConnectionError, AMQPError
from config.env import RabbitMQConfig
from utils.log_util import logger


class RabbitMQUtil:
    """
    RabbitMQ连接管理类
    """

    _connection: aio_pika.Connection | None = None

    @classmethod
    async def create_rabbitmq_pool(cls) -> aio_pika.Connection:
        """
        获取或创建缓存的RabbitMQ连接（connect_robust 自动处理重连）

        :return: RabbitMQ连接对象
        """
        if cls._connection is not None and not cls._connection.is_closed:
            return cls._connection
        logger.info('开始连接RabbitMQ...')
        try:
            cls._connection = await aio_pika.connect_robust(
                host=RabbitMQConfig.rabbitmq_host,
                port=RabbitMQConfig.rabbitmq_port,
                login=RabbitMQConfig.rabbitmq_username,
                password=RabbitMQConfig.rabbitmq_password,
                virtualhost=RabbitMQConfig.rabbitmq_vhost,
            )
            logger.info('RabbitMQ连接成功')
            return cls._connection
        except AMQPConnectionError as e:
            logger.error(f'RabbitMQ连接失败: {e}')
            raise
        except AMQPError as e:
            logger.error(f'RabbitMQ错误: {e}')
            raise

    @classmethod
    async def close_rabbitmq_pool(cls, app):
        """
        关闭RabbitMQ连接

        :param app: FastAPI应用对象
        :return:
        """
        if hasattr(app.state, 'rabbitmq') and app.state.rabbitmq:
            await app.state.rabbitmq.close()
            cls._connection = None
            logger.info('RabbitMQ连接已关闭')

    @classmethod
    async def publish_message(cls, routing_key: str, message_json: str, exchange_name: str = None):
        """
        使用缓存的连接发布消息，自动管理 channel 生命周期。
        """
        if exchange_name is None:
            exchange_name = RabbitMQConfig.rabbitmq_exchange
        conn = await cls.create_rabbitmq_pool()
        async with conn.channel() as channel:
            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.DIRECT, durable=True
            )
            await exchange.publish(
                aio_pika.Message(body=message_json.encode()),
                routing_key=routing_key,
            )

    @classmethod
    async def get_channel_pool(cls, app) -> aio_pika.Channel:
        """
        获取RabbitMQ通道

        :param app: FastAPI应用对象
        :return: RabbitMQ通道对象
        """
        if not hasattr(app.state, 'rabbitmq') or not app.state.rabbitmq:
            app.state.rabbitmq = await cls.create_rabbitmq_pool()

        return await app.state.rabbitmq.channel()

    @classmethod
    async def init_xuzhou_exchange_queue(cls, app, callback):
        """
        初始化徐州项目交换机和队列
        """
        channel = await cls.get_channel_pool(app)

        # 创建交换机
        exchange = await channel.declare_exchange(
            RabbitMQConfig.rabbitmq_exchange, aio_pika.ExchangeType.DIRECT, durable=True
        )

        # 创建队列
        queue = await channel.declare_queue(RabbitMQConfig.rabbitmq_queue, durable=True)

        # 绑定队列到交换机
        await queue.bind(exchange, routing_key=RabbitMQConfig.rabbitmq_routingkey)

        await queue.consume(callback)

        logger.info('徐州项目交换机和队列初始化完成')
