# ruoyi-fastapi-frontend — 智能视频分析平台前端

基于 Vue 3 + Vite + Element Plus 的前端应用，为智能视频分析平台提供 Web 管理界面。

## 目录结构

```
ruoyi-fastapi-frontend/
  src/
    main.js                  # Vue 应用入口，注册插件、全局组件
    permission.js             # 路由守卫：Token 校验、动态路由加载
    App.vue                   # 根组件
    router/
      index.js                # 路由配置（静态路由 + 动态路由）
    store/                    # Pinia 状态管理
      modules/
        permission.js          # 权限/菜单路由动态生成
        user.js                # 用户状态
        app.js                 # 应用全局状态
        settings.js            # 布局/主题设置
    api/                      # Axios API 封装
      login.js                 # 登录认证
      menu.js                  # 动态路由菜单
      binhua/                  # 振动心理分析模块
        analysis.js            # 分析记录 CRUD、PDF 报告导出
        people.js              # 人员管理、人脸比对
        agent.js               # AI Agent 对话（SSE 流式）
      xuzhou/                  # 视频监控模块
        video.js               # 摄像头 CRUD、推流配置
        camera.js              # 设备状态、快照、流地址
        algorithm.js           # 算法 CRUD、权重上传
        alarm.js               # 告警列表
        monitor.js             # 推理监控、缓存消息
        scene.js               # 场景管理
        clipAnalysis.js        # 视频片段截取与分析
      face/                    # 人脸模块
        people.js / group.js   # 人脸底库管理
      system/                  # 系统管理 API
      monitor/                 # 系统监控 API
      tool/                    # 开发工具 API
    views/                    # 页面组件
      binhua/                  # 振动心理分析页面
        analysis/index.vue     # 分析记录列表（首页）
        people/index.vue       # 人员信息管理
        agent/index.vue        # AI Agent 交互
      xz-monitor/              # 视频监控页面
        monitor/index.vue      # 监控仪表板
        camera-list/index.vue  # 摄像头列表与管理
        box-test/index.vue     # 边缘盒子调试
        clip-analysis/index.vue # 视频片段分析
        public-alarm/index.vue  # 公共场所告警
        road-alarm/index.vue    # 道路告警
        street-alarm/index.vue  # 街道告警
        danger-area/index.vue   # 危险区域检测
        human-density/index.vue # 人流密度监测
        object-structure/index.vue # 物体结构检测
        people-comparison/index.vue # 人员比对
      video/                   # 视频管理页面
      algorithm/               # 算法管理页面
      face/                    # 人脸底库页面
      system/                  # 系统管理页面（用户/角色/菜单等）
      monitor/                 # 系统监控页面（服务/缓存/日志等）
      tool/                    # 开发工具页面（代码生成等）
      dashboard/               # 仪表板
    components/               # 公共组件（文件上传、图标、编辑器等）
    layout/                   # 布局组件（侧边栏、导航栏、标签页）
    utils/                    # 工具函数
      request.js               # Axios 封装（拦截器、Token、错误处理）
      auth.js                  # Token 存取
      dict.js                  # 字典工具
    directive/                # 自定义指令
    plugins/                  # 插件注册
    assets/                   # 样式、图标、图片
  vite/
    plugins/                   # Vite 插件配置（压缩、SVG、自动导入）
  public/                     # 静态资源
  vite.config.js              # Vite 构建配置
  package.json                # 依赖与脚本
  .env.development             # 开发环境变量
  .env.production              # 生产环境变量
  .env.staging                 # 测试环境变量
```

## 技术栈

| 技术 | 用途 |
|------|------|
| **Vue 3.4** (Composition API) | 前端框架，`<script setup>` 语法 |
| **Vite 5** | 构建工具，HMR 热更新 |
| **Element Plus 2.7** | 主要 UI 组件库 |
| **Ant Design Vue 4.1** | 辅助 UI 组件（图表、图标） |
| **Pinia 2.1** | 状态管理 |
| **Vue Router 4.4** | 路由管理，History 模式 |
| **Axios 0.28** | HTTP 请求，请求/响应拦截器 |
| **ECharts 6.0 / AntV G2Plot** | 数据可视化图表 |
| **FLV.js 1.6** | HTTP-FLV 视频流播放 |
| **vue-cropper** | 图片裁剪（头像上传） |
| **vue-quill** | 富文本编辑器 |
| **markdown-it** | Markdown 渲染 |
| **jsencrypt** | 前端密码加密 |
| **SCSS / Less** | CSS 预处理 |

## 环境要求

- Node.js **16+**（推荐 18+）
- npm / yarn / pnpm

## 快速开始

### 1. 安装依赖

```bash
cd ruoyi-fastapi-frontend

# npm
npm install --registry=https://registry.npmmirror.com

# 或 yarn
yarn --registry=https://registry.npmmirror.com
```

### 2. 配置环境变量

开发环境配置文件为 `.env.development`：

```ini
# 后端 API 基础路径（开发环境由 Vite 代理转发到 http://127.0.0.1:9099）
VITE_APP_BASE_API = '/dev-api'

# 应用标题
VITE_APP_TITLE = '智能视频分析平台'
```

### 3. 启动开发服务器

```bash
npm run dev
```

开发服务器默认运行在 **端口 80**（`vite.config.js` 中配置）。

Vite 代理规则：

| 前端请求路径 | 代理目标 | 说明 |
|-------------|----------|------|
| `/dev-api/**` | `http://127.0.0.1:9099` | 后端 REST API（去掉 `/dev-api` 前缀） |
| `/openapi.json` | `http://127.0.0.1:9099` | Swagger JSON |
| `/api/proxy/**` | `http://192.168.0.246:8080` | 视频流代理 |

### 4. 访问

```
http://localhost:80
```

默认账号：`admin` / `admin123`

## 页面模块

### binhua — 振动心理分析

| 页面 | 路由 | 说明 |
|------|------|------|
| 分析记录 | `/index` (首页) | 心理状态分析记录列表，支持视频回放、PDF 报告导出 |
| 人员管理 | `/people` | 人脸信息录入、批量导入（Excel + ZIP）、特征提取 |
| AI Agent | `/agent` | 多模态 AI 对话（文本/图片/音频），7 日趋势统计 |

### xz-monitor — 视频监控

| 页面 | 路由 | 说明 |
|------|------|------|
| 监控仪表板 | `/xz-monitor/monitor` | 摄像头总数、运行/停止统计、搜索筛选 |
| 摄像头列表 | `/camera-list` | 设备状态监控、启停控制、实时快照、流播放 |
| 盒子调试 | `/box-test` | 边缘计算盒子通信调试 |
| 视频片段分析 | `/xz-monitor/clip-analysis` | 截图 + AI 分析（实时捕获 / 录制上传 / 离线分析） |
| 公共场所告警 | `/xz-monitor/public-alarm` | 公共场所告警事件列表 |
| 道路告警 | `/xz-monitor/road-alarm` | 道路告警事件列表 |
| 街道告警 | `/xz-monitor/street-alarm` | 街道告警事件列表 |
| 危险区域 | `/xz-monitor/danger-area` | 危险区域入侵检测 |
| 人流密度 | `/xz-monitor/human-density` | 区域人流密度监测 |
| 物体结构 | `/xz-monitor/object-structure` | 物体结构异常检测 |
| 人员比对 | `/xz-monitor/people-comparison` | 人员特征比对 |

### video / algorithm / face — 基础数据管理

| 页面 | 说明 |
|------|------|
| 视频管理 | 摄像头 CRUD，支持 Hikvision / RTSP / RTMP / 本地文件 |
| 算法管理 | 算法 CRUD，权重文件上传 |
| 人脸底库 | 人员分组管理，人脸比对 |

### system / monitor / tool — 系统管理

标准 RuoYi 管理功能：用户管理、角色管理、菜单管理、部门管理、岗位管理、字典管理、参数管理、通知公告、操作日志、登录日志、在线用户、定时任务、服务监控、缓存监控、代码生成。

## 构建部署

```bash
# 测试环境构建
npm run build:stage

# 生产环境构建
npm run build:prod

# 预览构建结果
npm run preview
```

构建产物输出到 `dist/` 目录，部署到 Nginx 等 Web 服务器即可。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name localhost;

    # 前端静态资源
    location / {
        root /path/to/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /prod-api/ {
        proxy_pass http://127.0.0.1:9099/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 配置参考

| 变量 | 说明 |
|------|------|
| `VITE_APP_BASE_API` | 后端 API 基础路径（开发 `/dev-api`，生产 `/prod-api`） |
| `VITE_APP_TITLE` | 应用标题（浏览器标签页显示） |

Vite 代理和构建输出路径等在 `vite.config.js` 中配置。
