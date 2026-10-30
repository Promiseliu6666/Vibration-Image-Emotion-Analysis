# 当前运行结构（2026-10-12）

摄像头 → watcher_usb.py → ws_handler.py → LatestFrames → analyzer.py → analysis_storage.py → 实时状态和提醒。

小智屏幕作为状态屏：analyzer.py 每帧把同一份 result 交给 state_sync.py，压成一条状态位命令 `study_sync`（状态码 + 标志位 + 连续用眼 / 屏幕累计 / 在位分钟），经 USB 串口控制台下发；屏幕上的字由固件用同一套状态码与标志位拼出（口径与页面一致），语音提醒也由固件按标志位自己决定播哪一种。固件端有效期 60 秒，服务端每 20 秒心跳续期，服务端停止后屏幕自动淡出，不会留下过时状态。老固件没有 `study_sync` 时自动退回文本命令 `study_state`，并继续由电脑侧播报，行为与之前一致。

预览独立于分析，保留最新 JPEG。当前高清 640×480 模式实测约 3 FPS；240×240 模式此前约 8–13 FPS，不能承诺同时达到同一帧率。每设备约两秒取一个分析样本，待分析队列同设备最多一张，旧图被替换。

analyzer.py 负责推理编排；phone_detector.py 负责实物与手部关联；temporal_analysis.py 负责连续确认；analysis_storage.py 负责时段、记录、图片归档和清理。

先保存原图和提交记录，再发布界面、语音提醒。提醒截图在 frames/alerts 长期保留；普通图片按设置清理。统计描述样本，不是完整录像或专注分钟数。

start.cmd 启动服务，open-project.cmd 打开网页，start-watcher.cmd 启动采集，stop.cmd 停止项目。后端统一关闭分析、广播及语音任务。

旧版依赖默认密码、真实联网并修改实际数据的测试已移出源码。保留本地回归，实际运行实例只进行授权的只读验证。

数据库初始化仍由 models.py/init_db.py 负责，analysis_schema.py 启动时补齐旧库所缺字段。旧版一次性迁移 SQL 已移除。

识别仍需真实场景准确率评估；多人前景关联不是身份识别。事件截图长期保存会占用磁盘，需定期备份；不能跟随普通图片自动清理。
