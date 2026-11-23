from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

from config.env import AppConfig
from config.get_db import init_create_table
from config.get_rabbitmq import RabbitMQUtil
from config.get_redis import RedisUtil
from config.get_scheduler import SchedulerUtil
from exceptions.handle import handle_exception
from middlewares.handle import handle_middleware
from module_admin.controller.cache_controller import cacheController
from module_admin.controller.callback_controller import callbackController
from module_admin.controller.captcha_controller import captchaController
from module_admin.controller.common_controller import commonController
from module_admin.controller.config_controller import configController
from module_admin.controller.dept_controller import deptController
from module_admin.controller.dict_controller import dictController
from module_admin.controller.job_controller import jobController
from module_admin.controller.log_controller import logController
from module_admin.controller.login_controller import loginController
from module_admin.controller.menu_controller import menuController
from module_admin.controller.manager_compat_controller import managerCompatController
from module_admin.controller.notice_controller import noticeController
from module_admin.controller.online_controller import onlineController
from module_admin.controller.post_controler import postController
from module_admin.controller.role_controller import roleController
from module_admin.controller.server_controller import serverController
from module_admin.controller.user_controller import userController
from module_generator.controller.gen_controller import genController
from module_xuzhou.controller.algorithm_controller import algorithmController
from module_xuzhou.controller.command_controller import message_callback, commandController
from module_xuzhou.controller.group_controller import group_controller
from module_xuzhou.controller.people_controller import people_controller
from module_xuzhou.controller.scene_controller import sceneController
from module_xuzhou.controller.video_controller import videoController
from module_xuzhou.controller.analysis_controller import analysis_controller
from module_xuzhou.controller.alarm_controller import alarmController
from module_xuzhou.controller.fatigue_controller import fatigue_controller
from module_task.monitor_controller import monitorController
from module_task.inference_monitor import start_inference_monitor
from sub_applications.handle import handle_sub_applications
from module_xuzhou.controller.agent_controller import agent_controller
from utils.log_util import logger
from hik_vision.hik_vision import videoController
from hik_vision.camera_bridge_config import get_camera_bridge_key
from hik_vision.fatigue_service import FatigueServiceSupervisor

# 生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_camera_bridge_key()
    logger.info(f'{AppConfig.app_name}开始启动')
    await init_create_table()
    app.state.redis = await RedisUtil.create_redis_pool()
    await RedisUtil.init_sys_dict(app.state.redis)
    await RedisUtil.init_sys_config(app.state.redis)
    if os.getenv('LOCAL_DISABLE_RABBITMQ', 'false').lower() != 'true':
        app.state.rabbitmq = await RabbitMQUtil.create_rabbitmq_pool()
        await RabbitMQUtil.init_xuzhou_exchange_queue(app, message_callback)
    else:
        logger.warning('Local mode: external RabbitMQ workers disabled')
    await SchedulerUtil.init_system_scheduler()
    
    # 启动推理监控器（在后台任务中运行）
    if os.getenv('LOCAL_DISABLE_INFERENCE_MONITOR', 'false').lower() != 'true':
        asyncio.create_task(start_inference_monitor())
        logger.info(f'{AppConfig.app_name}推理监控器已启动')
    
    app.state.fatigue_service = FatigueServiceSupervisor()
    app.state.fatigue_service.start()
    logger.info(f'{AppConfig.app_name}启动成功')
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.fatigue_service.stop)
    await RedisUtil.close_redis_pool(app)
    await RabbitMQUtil.close_rabbitmq_pool(app)
    await SchedulerUtil.close_system_scheduler()


# 初始化FastAPI对象
app = FastAPI(
    title=AppConfig.app_name,
    description=f'{AppConfig.app_name}能力接口文档',
    version=AppConfig.app_version,
    lifespan=lifespan,
    docs_url=None,  # 禁用默认的docs URL
    swagger_ui_parameters={'defaultModelsExpandDepth': -1},
)

# 挂载子应用
handle_sub_applications(app)
# 加载中间件处理方法
handle_middleware(app)
# 加载全局异常处理方法
handle_exception(app)

# 加载路由列表
controller_list = [
    {'router': loginController, 'tags': ['登录模块']},
    {'router': captchaController, 'tags': ['验证码模块']},
    {'router': userController, 'tags': ['系统管理-用户管理']},
    {'router': roleController, 'tags': ['系统管理-角色管理']},
    {'router': menuController, 'tags': ['系统管理-菜单管理']},
    {'router': deptController, 'tags': ['系统管理-部门管理']},
    {'router': postController, 'tags': ['系统管理-岗位管理']},
    {'router': dictController, 'tags': ['系统管理-字典管理']},
    {'router': configController, 'tags': ['系统管理-参数管理']},
    {'router': noticeController, 'tags': ['系统管理-通知公告管理']},
    {'router': logController, 'tags': ['系统管理-日志管理']},
    {"router" : videoController,'tags': ['系统监控-数据监控']},
    {'router': onlineController, 'tags': ['系统监控-在线用户']},
    {'router': jobController, 'tags': ['系统监控-定时任务']},
    {'router': serverController, 'tags': ['系统监控-菜单管理']},
    {'router': cacheController, 'tags': ['系统监控-缓存监控']},
    {'router': callbackController, 'tags': ['工具-回调管理']},
    {'router': commonController, 'tags': ['通用模块']},
    {'router': genController, 'tags': ['代码生成']},
    {'router': algorithmController, 'tags': ['算法列表']},
    {'router': sceneController, 'tags': ['场景列表']},
    {'router': analysis_controller,'tags':['分析列表']},
    {'router': fatigue_controller,'tags':['疲劳检测']},
    {'router': commandController, 'tags': ['场景监控']},
    {'router': alarmController, 'tags': ['预警管理']},
    {'router': people_controller, 'tags': ['人员']},
    {'router': group_controller, 'tags': ['人员组']},
    {'router': monitorController, 'tags': ['推理监控']},
    {'router': agent_controller, 'tags': ['AI Agent']}
]


# 自定义Swagger UI路由，使用本地静态文件
@app.get('/docs', include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + ' - Swagger UI',
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url='/static/swagger-ui/swagger-ui-bundle.js',
        swagger_css_url='/static/swagger-ui/swagger-ui.css',
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


for controller in controller_list:
    app.include_router(router=controller.get('router'), tags=controller.get('tags'))

app.include_router(router=managerCompatController, tags=['Manager API Compatibility'])

from xiaozhi_integration import router as xiaozhi_integration_router
app.include_router(xiaozhi_integration_router)

from module_interaction.rest_controller import rest_controller
app.include_router(rest_controller, tags=["互动休息室"])
