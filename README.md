<p align="center">
	<img alt="logo" src="https://oscimg.oschina.net/oscnet/up-d3d0a9303e11d522a06cd263f3079027715.png">
</p>
<h1 align="center" style="margin: 30px 0 30px; font-weight: bold;">RuoYi-Vue3-FastAPI v1.6.2</h1>
<h4 align="center">基于RuoYi-Vue3+FastAPI前后端分离的快速开发框架</h4>

## 平台简介

RuoYi-Vue3-FastAPI是一套全部开源的快速开发平台，毫无保留给个人及企业免费使用。

* 前端采用Vue3、Element Plus，基于<u>[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)</u>前端项目修改。
* 后端采用FastAPI、sqlalchemy、MySQL（PostgreSQL）、Redis、OAuth2 & Jwt。
* 权限认证使用OAuth2 & Jwt，支持多终端认证系统。
* 支持加载动态权限菜单，多方式轻松权限控制。
* Vue2版本：
    - Gitte仓库地址：https://gitee.com/insistence2022/RuoYi-Vue-FastAPI
    - GitHub仓库地址：https://github.com/insistence/RuoYi-Vue-FastAPI
* 纯Python版本：
    - Gitte仓库地址：https://gitee.com/insistence2022/dash-fastapi-admin
    - GitHub仓库地址：https://github.com/insistence/Dash-FastAPI-Admin
* 特别鸣谢：<u>[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)</u>

## 内置功能

1. 用户管理：用户是系统操作者，该功能主要完成系统用户配置。
2. 角色管理：角色菜单权限分配、设置角色按机构进行数据范围权限划分。
3. 菜单管理：配置系统菜单，操作权限，按钮权限标识等。
4. 部门管理：配置系统组织机构（公司、部门、小组）。
5. 岗位管理：配置系统用户所属担任职务。
6. 字典管理：对系统中经常使用的一些较为固定的数据进行维护。
7. 参数管理：对系统动态配置常用参数。
8. 通知公告：系统通知公告信息发布维护。
9. 操作日志：系统正常操作日志记录和查询；系统异常信息日志记录和查询。
10. 登录日志：系统登录日志记录查询包含登录异常。
11. 在线用户：当前系统中活跃用户状态监控。
12. 定时任务：在线（添加、修改、删除）任务调度包含执行结果日志。
13. 服务监控：监视当前系统CPU、内存、磁盘、堆栈等相关信息。
14. 缓存监控：对系统的缓存信息查询，命令统计等。
15. 在线构建器：拖动表单元素生成相应的HTML代码。
16. 系统接口：根据业务代码自动生成相关的api接口文档。
17. 代码生成：配置数据库表信息一键生成前后端代码（python、sql、vue、js），支持下载。

## 项目开发及发布相关

### 开发

```bash
# 克隆项目
git clone https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI.git

# 进入项目根目录
cd RuoYi-Vue3-FastAPI
```

#### 前端

```bash
# 进入前端目录
cd ruoyi-fastapi-frontend

# 安装依赖
npm install 或 yarn --registry=https://registry.npmmirror.com

# 建议不要直接使用 cnpm 安装依赖，会有各种诡异的 bug。可以通过如下操作解决 npm 下载速度慢的问题
npm install --registry=https://registry.npmmirror.com

# 启动服务
npm run dev 或 yarn dev
```

#### 后端

```bash
# 进入后端目录
cd ruoyi-fastapi-backend

# 如果使用的是MySQL数据库，请执行以下命令安装项目依赖环境
uv sync
# 如果使用的是PostgreSQL数据库，请执行以下命令安装项目依赖环境
pip3 install -r requirements-pg.txt

# 配置环境
在.env.dev文件中配置开发环境的数据库和redis

# 运行sql文件
1.新建数据库ruoyi-fastapi(默认，可修改)
2.如果使用的是MySQL数据库，使用命令或数据库连接工具运行sql文件夹下的ruoyi-fastapi.sql；如果使用的是PostgreSQL数据库，使用命令或数据库连接工具运行sql文件夹下的ruoyi-fastapi-pg.sql

# 运行后端
uv run app.py --env=dev
```

#### 访问

```bash
# 默认账号密码
账号：admin
密码：admin123

# 浏览器访问
地址：http://localhost:80
```

### 发布

#### 前端

```bash
# 构建测试环境
npm run build:stage 或 yarn build:stage

# 构建生产环境
npm run build:prod 或 yarn build:prod
```

#### 后端

```bash
# 配置环境
在.env.prod文件中配置生产环境的数据库和redis

# 运行后端
uv run app.py --env=prod
```

## 智能视频分析平台

本项目在 RuoYi-Vue3-FastAPI 框架基础上，构建了一套完整的**智能视频分析平台**，支持边缘盒子 + 本地服务端双模式部署，覆盖人脸检测、特征识别、心理状态振动分析等场景。

### 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (Vue3 + Vite)                         │
│                  端口 80，Nginx 反代到后端 /dev-api                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP REST API
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI + Uvicorn)                        │
│  端口 9099                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ 系统管理  │ │ 视频管理  │ │ 算法管理  │ │ 振动心理分析 (Binhua) │  │
│  │ (RBAC)   │ │ (摄像头)  │ │ (调度)   │ │ 人员管理 · AI Agent  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
│                                                                  │
│  MySQL/PostgreSQL ◀── 数据持久化                                  │
│  Redis ◀── 会话缓存 / 系统配置                                     │
└──────────────────────────────┬───────────────────────────────────┘
                               │ RabbitMQ (xuzhou exchange)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    边缘盒子 (Ascend NPU)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ ffmpeg 推流   │  │ OpenCV 取帧   │  │ 算法插件 (热加载)      │   │
│  │ (观看通道)    │  │ (推理通道)    │  │ face_detection       │   │
│  │ -c copy → SRS │  │ → NPU 推理   │  │ arcface_recognition  │   │
│  └──────────────┘  └──────────────┘  │ realtime_face_analysis│   │
│                                       └──────────────────────┘   │
│  本地 HTTP API (端口 9100): 健康检查 · 快照 · MJPEG 流             │
└──────────────────────────────────────────────────────────────────┘
```

### 业务功能

| 功能模块 | 说明 |
|----------|------|
| **摄像头管理** | 支持 RTSP / RTMP / Hikvision / 本地 USB 摄像头，统一管理推流与录制 |
| **算法调度** | 算法插件热加载，支持人脸检测、ArcFace 特征提取、实时幸福指数分析 |
| **边缘盒子** | 华为 Ascend NPU 推理，RabbitMQ 双向通信，心跳保活，自动拉流恢复 |
| **设备状态** | 盒子/摄像头在线状态实时监控，设备心跳上报，异常自动告警 |
| **振动心理分析** | 基于面部微振动的 14 维心理生理参数分析（e1~e14），幸福指数、外向性、稳定性评估 |
| **人员管理** | 人脸底库管理，特征向量提取与比对，批量导入导出 |
| **告警系统** | RabbitMQ 实时告警消息，分类展示（道路/街道/公共场所），历史告警回溯 |
| **AI Agent** | 多模态 AI 对话（文本/图片/音频），对话历史，统计分析，7 日趋势 |
| **实时分析** | 本地 DNN 人脸检测 + ArcFace 人脸识别 + Vibraimage 幸福分析，MJPEG 直播展示 |
| **分析报告** | 心理状态 PDF 报告导出，分析记录 CRUD，视频回放 |
| **视频片段分析** | 摄像头截图 + AI 分析，支持实时捕获、录制上传、离线分析三种模式 |
| **RBAC 权限** | 用户/角色/菜单/部门/岗位管理，动态权限菜单，数据范围权限控制 |
| **系统监控** | 服务监控（CPU/内存/磁盘）、缓存监控、定时任务、操作日志、登录日志 |

### 项目结构

| 目录 | 说明 | 详细文档 |
|------|------|----------|
| `ruoyi-fastapi-backend/` | FastAPI 后端服务，提供 REST API、业务逻辑、后台调度 | [后端 README](ruoyi-fastapi-backend/README.md) |
| `ruoyi-fastapi-frontend/` | Vue3 前端应用，提供 Web 管理界面 | [前端 README](ruoyi-fastapi-frontend/README.md) |
| `binhua_box/` | 昇腾边缘盒子服务，负责摄像头拉流与 NPU 推理 | [盒子 README](binhua_box/README.md) |
