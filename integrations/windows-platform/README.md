# Windows 桌面启动文件

将本目录中的三个 Python 文件、三个 CMD 文件和 `employee-portal` 文件夹复制到项目外层目录。内层源码文件夹命名为 `Vibration-Image-Emotion-Analysis-main`，结构如下。

```text
外层目录/
  local_services.py
  start_interactive_rest.py
  restart_health.py
  启动健康监测平台.cmd
  启动互动休息室.cmd
  重启健康监测平台.cmd
  employee-portal/
    start_all.py
    server.py
  Vibration-Image-Emotion-Analysis-main/
    ruoyi-fastapi-backend/
    ruoyi-fastapi-frontend/
    xiaozhi-study/
```

使用本机已配置的后端虚拟环境、前端依赖、`.env.dev`、数据库和缓存服务。双击“启动健康监测平台.cmd”启动服务后，访问下方原系统地址。“启动互动休息室.cmd”会在服务就绪后打开休息室页面。旧地址 `http://127.0.0.1:8800/` 会跳转到 `http://127.0.0.1:5173/`。

小智默认优先使用内层 `xiaozhi-study` 源码与其本地运行环境，也支持通过 `XIAOZHI_RUNTIME_DIR`、`XIAOZHI_PYTHON` 和 `XIAOZHI_LEGACY_PROJECT_DIR` 复用本机已有安装。单点登录和摄像头共享密钥沿用本机配对配置。

“重启健康监测平台.cmd”重启已识别的应用后端。服务启动时会检查实际接口，小智和疲劳模型服务的独立故障会显示在启动窗口。设置 `XIAOZHI_RESUME_USB=0` 可以在调试启动时关闭 USB 采集恢复。
