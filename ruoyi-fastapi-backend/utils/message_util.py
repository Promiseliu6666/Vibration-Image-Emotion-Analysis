import aio_pika
from aio_pika.exceptions import AMQPError
from config.env import RabbitMQConfig
from config.get_rabbitmq import RabbitMQUtil
from utils.log_util import logger


class RabbitMQService:
    """
    RabbitMQ消息服务工具类
    """

    @classmethod
    async def send_message(cls, app, queue_name: str, message: str):
        """
        发送消息到指定队列

        :param app: FastAPI应用对象
        :param queue_name: 队列名称
        :param message: 消息内容
        """
        try:
            channel = await RabbitMQUtil.get_channel_pool(app)

            # 声明交换机
            exchange = await channel.declare_exchange(
                RabbitMQConfig.rabbitmq_exchange, aio_pika.ExchangeType.DIRECT, durable=True
            )

            # 发送消息到指定交换机
            await exchange.publish(aio_pika.Message(body=message.encode()), routing_key=queue_name)
            logger.info(f'成功发送消息到交换机 {RabbitMQConfig.rabbitmq_exchange}，队列 {queue_name}: {message}')
        except AMQPError as e:
            logger.error(f'发送消息到交换机 {RabbitMQConfig.rabbitmq_exchange}，队列 {queue_name} 失败: {e}')
            raise

    @classmethod
    async def consume_messages(cls, app, queue_name: str, callback):
        """
        消费指定队列消息

        :param app: FastAPI应用对象
        :param queue_name: 队列名称
        :param callback: 消息处理回调函数
        """
        try:
            channel = await RabbitMQUtil.get_channel_pool(app)
            queue = await channel.declare_queue(f'{RabbitMQConfig.rabbitmq_queue_prefix}{queue_name}', durable=True)
            await queue.consume(callback)
            logger.info(f'开始消费队列 {queue.name} 的消息')
        except AMQPError as e:
            logger.error(f'消费队列 {queue_name} 消息失败: {e}')
            raise


def message_service(sms_code: str):
    logger.info(f'短信验证码为{sms_code}')
