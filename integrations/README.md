# 小智健康监测集成说明

完整的小智服务源码现已合并到仓库内的 `xiaozhi-study/`，后续开发以该目录为唯一源码来源：

- 小智后端：`xiaozhi-study/app/`
- 小智页面与静态资源：`xiaozhi-study/static/`
- 门户后端集成：`ruoyi-fastapi-backend/xiaozhi_integration.py`
- 门户前端入口：`ruoyi-fastapi-frontend/src/views/xiaozhi/`
- 统一启动入口：项目根目录的 `start-local.cmd`

原 `xiaozhi-overlay/` 中的 16 个文件与 `xiaozhi-study/` 对应源码完全一致，因此已经移除。不要再维护一份独立的补丁副本，否则两边修改后容易出现运行版本和源码不一致。

服务运行端口：

- 门户前端：`5173`
- 门户后端：`9099`
- 小智后端：`8000`
- 门户数据库：`13306`
- 小智数据库：`3307`

`start-local.cmd` 会同时启动上述服务。`.runtime/`、`.venv/`、模型权重、日志、截图和数据库文件保留在本机，不提交到 Git。单点登录密钥和摄像头桥接密钥仍由各自运行目录的 `.runtime/` 保存，两个系统使用的密钥内容必须一致。

`windows-platform/` 中的桌面外层启动文件属于旧部署兼容入口，当前统一启动应使用根目录的 `start-local.cmd`。
