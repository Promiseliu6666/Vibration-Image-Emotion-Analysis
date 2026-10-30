"""数据库连接管理"""
import pymysql
from pymysql.cursors import DictCursor
from app.core.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

def get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        connect_timeout=5,
        read_timeout=20,
        write_timeout=20,
        cursorclass=DictCursor,
    )
