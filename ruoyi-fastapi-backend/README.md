# ruoyi-fastapi-backend — 智能视频分析平台后端

基于 FastAPI + SQLAlchemy async 的后端服务，为智能视频分析平台提供 REST API、业务逻辑、后台调度与边缘盒子通信能力。

## 目录结构

```
ruoyi-fastapi-backend/
  app.py                     # Uvicorn 入口，启动 FastAPI 应用
  server.py                  # FastAPI 应用工厂：生命周期、中间件、路由注册
  pyproject.toml             # 项目元数据与依赖（uv 管理）
  Dockerfile                 # Docker 容器构建
  config/                    # 配置模块
    env.py                   # 环境变量加载（pydantic-settings）
    database.py              # SQLAlchemy async 引擎与会话
    redis.py                 # Redis 连接池
    rabbitmq.py              # RabbitMQ 连接池与消息收发
    srs.py                   # SRS 流媒体服务器配置
    jwt.py                   # JWT 认证配置
  module_admin/              # 系统管理模块（RBAC）
    controller/              # 用户 · 角色 · 菜单 · 部门 · 岗位 · 字典 · 日志等
    service/                 # 业务逻辑
    dao/                     # 数据访问
    entity/do/vo/            # ORM 模型 / Pydantic 模型
  module_xuzhou/             # 视频分析业务模块
    controller/              # 摄像头 · 算法 · 场景 · 告警 · 分析 · 人员 · Agent
    service/                 # 业务逻辑（含人脸特征提取 ONNX worker）
    dao/                     # 数据访问
    entity/do/vo/            # ORM 模型 / Pydantic 模型
  module_task/               # 后台任务调度
    inference_monitor.py     # 推理监控（5 分钟周期检查）
    streaming_checker.py     # 推流状态检查
    video_ai.py              # 单路摄像头推理启动
    scheduler_test.py        # 调度测试工具
  module_generator/          # 代码生成器（RuoYi 风格）
  hik_vision/                # 本地实时分析模块
    hik_vision.py            # DNN 人脸检测 + 振动分析 MJPEG 流
    Vibration_image_algorithm.py  # VibraimageCore 14 维心理参数提取
    local_video_analysis.py  # 本地分析能力判定
    email_service.py         # 告警邮件服务
  algorithm/                 # 算法运行时抽象
    runtime_service.py       # 算法绑定解析 · 运行注册表
  sub_applications/          # 挂载子应用（静态文件等）
  exceptions/                # 全局异常处理
  middlewares/               # CORS · GZip · Trace 中间件
  utils/                     # 日志 · 分页 · 响应格式 · Excel · 上传 · 模板
  nodejs/                    # Node.js 辅助脚本
  sql/                       # 数据库初始化 SQL
    ruoyi-fastapi.sql        # MySQL 建表脚本
    ruoyi-fastapi-pg.sql     # PostgreSQL 建表脚本
  tests/                     # 测试用例
  scripts/                   # 构建/部署脚本
  .env.dev / .env.prod       # 环境配置文件
```

## 技术栈

| 技术 | 用途 |
|------|------|
| **FastAPI** + **Uvicorn** | Web 框架与 ASGI 服务器 |
| **SQLAlchemy 2.0 async** | 异步 ORM（asyncmy / asyncpg） |
| **MySQL** / **PostgreSQL** | 主数据库 |
| **Redis** | 会话缓存、系统字典与配置缓存 |
| **RabbitMQ** (aio-pika) | 边缘盒子消息通信（命令下发、结果回传、设备状态） |
| **APScheduler** | Cron 定时任务调度 |
| **OAuth2 + JWT** | 前后端分离认证，支持多终端 |
| **SRS** | RTMP/FLV 流媒体服务器（摄像头推流与前端播放） |
| **ONNX Runtime** | ArcFace 人脸特征提取（w600k_r50） |
| **OpenCV DNN** | Caffe SSD 人脸检测 |
| **PaddleX / PaddlePaddle** | CV 模型推理框架 |
| **ReportLab** | PDF 心理分析报告生成 |
| **Loguru** | 结构化日志 |

## 环境要求

- Python **3.12+**
- MySQL 8.0+ 或 PostgreSQL 14+
- Redis 6.0+
- RabbitMQ 3.9+
- SRS（Simple Realtime Server，用于视频推流/拉流）
- ONNX Runtime（可选，人脸特征提取）

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd vision_algorithm_admin/ruoyi-fastapi-backend
```

### 2. 安装依赖

```bash
# 使用 uv（推荐，MySQL 环境）
uv sync

# 使用 pip（PostgreSQL 环境）
pip3 install -r requirements-pg.txt
```

### 3. 配置环境

编辑 `.env.dev`，配置数据库、Redis 和 RabbitMQ 连接信息：

```ini
# 应用
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=9099

# 数据库（MySQL 示例）
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USERNAME=root
DB_PASSWORD=your_password
DB_DATABASE=ruoyi-fastapi

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# RabbitMQ
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
```

### 4. 初始化数据库

```bash
# MySQL
mysql -u root -p ruoyi-fastapi < sql/ruoyi-fastapi.sql

# PostgreSQL
psql -U postgres ruoyi-fastapi < sql/ruoyi-fastapi-pg.sql
```

### 5. 启动服务

```bash
# 开发环境
uv run app.py --env=dev

# 生产环境
uv run app.py --env=prod
```

启动成功日志：

```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:9099
INFO:     Application startup complete.
```

### 6. 访问

- API 文档（Swagger UI）：`http://localhost:9099/docs`
- 默认账号：`admin` / `admin123`

## 核心模块

### module_admin — 系统管理

标准 RuoYi RBAC 权限体系：用户、角色、菜单、部门、岗位、字典、参数、通知公告、操作日志、登录日志、在线用户、定时任务、服务监控、缓存监控。

### module_xuzhou — 视频分析业务

| 子模块 | 路由前缀 | 说明 |
|--------|----------|------|
| 视频管理 | `/xuzhou/video` | 摄像头 CRUD，支持 RTSP / RTMP / Hikvision / 本地 USB，推流到 SRS |
| 算法管理 | `/xuzhou/algorithm` | 算法 CRUD、权重上传、统计图表 |
| 场景管理 | `/xuzhou/scene` | 场景 CRUD，摄像头与算法绑定配置 |
| 设备控制 | `/xuzhou/command` | 核心操作接口：推送视频配置、设备状态缓存、盒子注册、流地址、快照、MJPEG 代理 |
| 告警管理 | `/xuzhou/alarm` | 告警消息列表查询 |
| 推理监控 | `/xuzhou/monitor` | 推理状态、任务详情、推流检查、定时任务配置 |
| 心理分析 | `/analysis` | 振动分析记录 CRUD、PDF 报告导出、视频文件服务（本地 & 盒子代理） |
| 人员管理 | `/people` | 人员 CRUD、人脸特征提取与比对 |
| 人员组 | `/group` | 人员分组管理 |
| AI Agent | `/agent` | 多模态 AI 对话（SSE 流式）、对话历史、统计分析 |

### hik_vision — 本地实时分析

无需边缘盒子，在服务端直接运行人脸检测 + 振动分析：

- DNN 人脸检测（OpenCV Caffe SSD）
- ArcFace 人脸特征提取与底库比对
- VibraimageCore 14 维心理生理参数分析（e1~e14）
- MJPEG 实时画面流：`/video/feed/analysis`
- 低幸福指数邮件告警

### module_task — 后台调度

- `InferenceMonitor`：每 5 分钟检查应运行的摄像头并自动启停推理
- `StreamingChecker`：验证 SRS 推流状态
- APScheduler 定时任务：支持 cron 表达式配置摄像头定时启停

### 认证体系

`module_xuzhou/auth.py` 提供统一认证依赖 `unified_auth`，同时支持：

1. **JWT Bearer Token** — Web 前端用户
2. **X-API-Token** — 边缘盒子 / 设备调用

## API 文档

启动后端后访问 Swagger UI：

```
http://localhost:9099/docs
```

所有接口按 Tag 分组（系统管理、徐州视频管理、算法列表、场景监控、预警管理等），支持在线调试。

## 配置参考

完整配置项见 `.env.dev` / `.env.prod`，关键环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `dev` | 运行环境（dev / prod） |
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `9099` | 监听端口 |
| `APP_ROOT_PATH` | `/dev-api` | 根路径前缀 |
| `DB_TYPE` | `mysql` | 数据库类型（mysql / postgresql） |
| `DB_HOST` | `127.0.0.1` | 数据库地址 |
| `DB_PORT` | `3306` | 数据库端口 |
| `DB_DATABASE` | `ruoyi-fastapi` | 数据库名称 |
| `REDIS_HOST` | `127.0.0.1` | Redis 地址 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `RABBITMQ_HOST` | `127.0.0.1` | RabbitMQ 地址 |
| `RABBITMQ_PORT` | `5672` | RabbitMQ 端口 |
| `SRS_RTMP_HOST` | `127.0.0.1` | SRS RTMP 地址 |
| `SRS_RTMP_PORT` | `1935` | SRS RTMP 端口 |
| `SRS_FLV_PORT` | `8080` | SRS HTTP-FLV 端口 |
| `JWT_SECRET_KEY` | — | JWT 签名密钥（生产环境务必修改） |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 过期时间（分钟） |
