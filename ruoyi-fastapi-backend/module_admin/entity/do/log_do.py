from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text
from config.database import Base


class SysLogininfor(Base):
    """
    系统访问记录
    """

    __tablename__ = 'sys_logininfor'

    info_id = Column(Integer, primary_key=True, autoincrement=True, comment='访问ID')
    user_name = Column(String(50), nullable=True, default='', comment='用户账号')
    ipaddr = Column(String(128), nullable=True, default='', comment='登录IP地址')
    login_location = Column(String(255), nullable=True, default='', comment='登录地点')
    browser = Column(String(50), nullable=True, default='', comment='浏览器类型')
    os = Column(String(50), nullable=True, default='', comment='操作系统')
    status = Column(String(1), nullable=True, default='0', comment='登录状态（0成功 1失败）')
    msg = Column(String(255), nullable=True, default='', comment='提示消息')
    login_time = Column(DateTime, nullable=True, default=datetime.now(), comment='访问时间')

    idx_sys_logininfor_s = Index('idx_sys_logininfor_s', status)
    idx_sys_logininfor_lt = Index('idx_sys_logininfor_lt', login_time)


class SysOperLog(Base):
    """
    操作日志记录
    """

    __tablename__ = 'sys_oper_log'

    oper_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='日志主键')
    title = Column(String(50), nullable=True, default='', comment='模块标题')
    business_type = Column(Integer, default=0, comment='业务类型（0其它 1新增 2修改 3删除）')
    method = Column(String(100), nullable=True, default='', comment='方法名称')
    request_method = Column(String(10), nullable=True, default='', comment='请求方式')
    operator_type = Column(Integer, default=0, comment='操作类别（0其它 1后台用户 2手机端用户）')
    oper_name = Column(String(50), nullable=True, default='', comment='操作人员')
    dept_name = Column(String(50), nullable=True, default='', comment='部门名称')
    oper_url = Column(String(255), nullable=True, default='', comment='请求URL')
    oper_ip = Column(String(128), nullable=True, default='', comment='主机地址')
    oper_location = Column(String(255), nullable=True, default='', comment='操作地点')
    oper_param = Column(String(2000), nullable=True, default='', comment='请求参数')
    json_result = Column(String(2000), nullable=True, default='', comment='返回参数')
    status = Column(Integer, default=0, comment='操作状态（0正常 1异常）')
    error_msg = Column(String(2000), nullable=True, default='', comment='错误消息')
    oper_time = Column(DateTime, nullable=True, default=datetime.now(), comment='操作时间')
    cost_time = Column(BigInteger, default=0, comment='消耗时间')

    idx_sys_oper_log_bt = Index('idx_sys_oper_log_bt', business_type)
    idx_sys_oper_log_s = Index('idx_sys_oper_log_s', status)
    idx_sys_oper_log_ot = Index('idx_sys_oper_log_ot', oper_time)


class SysIntegrationLog(Base):
    """
    系统对接日志记录
    """

    __tablename__ = 'xuzhou_integration_log'

    log_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='日志主键')
    system_name = Column(String(100), nullable=True, default='', comment='系统名称')
    interface_name = Column(String(100), nullable=True, default='', comment='接口名称')
    interface_url = Column(String(500), nullable=True, default='', comment='接口地址')
    request_method = Column(String(10), nullable=True, default='', comment='请求方式')
    request_params = Column(Text, nullable=True, default='', comment='请求参数')
    response_data = Column(Text, nullable=True, default='', comment='响应数据')
    status = Column(Integer, default=0, comment='请求状态（0成功 1失败）')
    error_msg = Column(Text, nullable=True, default='', comment='错误信息')
    request_time = Column(DateTime, nullable=True, default=datetime.now(), comment='请求时间')
    response_time = Column(DateTime, nullable=True, comment='响应时间')
    cost_time = Column(BigInteger, default=0, comment='耗时（毫秒）')
    request_ip = Column(String(128), nullable=True, default='', comment='请求IP')
    user_agent = Column(String(500), nullable=True, default='', comment='用户代理')
    trace_id = Column(String(64), nullable=True, default='', comment='链路追踪ID')
    remark = Column(String(500), nullable=True, default='', comment='备注')

    idx_sys_integration_log_sn = Index('idx_sys_integration_log_sn', system_name)
    idx_sys_integration_log_s = Index('idx_sys_integration_log_s', status)
    idx_sys_integration_log_rt = Index('idx_sys_integration_log_rt', request_time)
