import bcrypt
from passlib.context import CryptContext

# Legacy accounts may use PBKDF2; bcrypt uses its native implementation to
# avoid passlib's incompatibility with recent bcrypt releases.
pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
BCRYPT_PREFIXES = ('$2a$', '$2b$', '$2y$')


class PwdUtil:
    """
    密码工具类
    """

    @classmethod
    def verify_password(cls, plain_password, hashed_password):
        """
        工具方法：校验当前输入的密码与数据库存储的密码是否一致

        :param plain_password: 当前输入的密码
        :param hashed_password: 数据库存储的密码
        :return: 校验结果
        """
        if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
            return False
        if not plain_password or not hashed_password:
            return False
        try:
            if hashed_password.startswith(BCRYPT_PREFIXES):
                return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
            return pwd_context.verify(plain_password, hashed_password)
        except (ValueError, TypeError):
            # UnknownHashError is a ValueError; malformed and unsupported
            # stored hashes must produce an ordinary authentication failure.
            return False

    @classmethod
    def get_password_hash(cls, input_password):
        """
        工具方法：对当前输入的密码进行加密

        :param input_password: 输入的密码
        :return: 加密成功的密码
        """
        return bcrypt.hashpw(input_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
