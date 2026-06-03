# binhua_box — 昇腾盒子端服务

基于华为 Ascend NPU 的边缘视频分析服务，负责摄像头拉流、算法推理、结果回传。

> 本目录是[智能视频分析平台](../README.md)的边缘计算组件，与后端通过 RabbitMQ 通信。

## 目录结构

```
binhua_box/
  main.py                  # 服务入口
  config.py                # 配置（环境变量读取）
  models.py                # 内部数据模型
  camera_manager.py        # 摄像头管理（ffmpeg 推流 + OpenCV 取帧）
  algorithm_runner.py      # 算法调度引擎（插件加载、帧分发、结果收拢）
  rabbitmq_client.py       # RabbitMQ 通信（命令接收、结果上报、心跳）
  local_api.py             # 本地 HTTP API（健康检查、快照、流地址）
  engine/                  # 推理引擎层
    face_detector_ascend.py   # Ascend NPU 人脸检测
    arcface_ascend.py         # Ascend NPU 人脸特征提取
    vibraimage.py             # CPU 幸福指数分析
    face_detector.py          # 对外统一导出 FaceDetector
  algorithms/              # 算法插件（每个文件一个算法）
    face_detection.py         # 人脸检测
    arcface_recognition.py    # 人脸特征识别
    realtime_face_analysis.py # 实时幸福指数分析
  weights/                 # 模型权重目录
    face_detection.om         # ATC 转换后的人脸检测模型 (Ascend)
    arcface.om                # ATC 转换后的 ArcFace 模型 (Ascend)
```

## 架构

### 双通道隔离设计

```
                          ┌─────────────────────────┐
  摄像头 RTSP ───────────▶│ ffmpeg (独立进程)        │──▶ SRS ──▶ 前端观看
                          │ -c copy，零 CPU 开销     │
                          │                          │
  摄像头 RTSP ───────────▶│ OpenCV (独立连接)        │──▶ 算法推理
                          │ 解码帧 → NPU 推理        │
                          └─────────────────────────┘
```

- **通道 1（观看）**：ffmpeg 直接拉 RTSP，`-c copy` 不编解码，零 CPU 开销推 SRS
- **通道 2（推理）**：OpenCV 单独拉 RTSP 解码，送 Ascend NPU 推理
- 两条通道独立进程、独立 RTSP 连接，互不阻塞

### 数据流

```
后端 push_video_config API
  │
  ▼
RabbitMQ (routing_key: algorithm_{BOX_SERIAL})
  │
  ▼
main._handle_backend_command()
  ├─ camera_manager.start_camera()   # 启动 ffmpeg + OpenCV
  └─ runner.set_algorithms()         # 加载算法插件
  │
  ▼
camera_manager._read_loop()         # 持续读取帧
  │
  ▼
algorithm_runner.process_frame()    # 帧分发到各算法插件
  │
  ├─ face_detection.infer()         # 检测人脸 → bbox
  ├─ arcface_recognition.infer()    # 人脸裁剪 → 特征提取 → base64
  └─ realtime_face_analysis.infer() # 稳定追踪 → 幸福指数 e1~e14
  │
  ▼
_on_algorithm_result()             # 结果收集到 _pending_results
  │
  ▼
_periodic_result_flush()           # 每秒批量发送
  │
  ▼
RabbitMQ (routing_key: api_service, type: alarm)
  │
  ▼
后端 message_callback
  ├─ AlarmService.save_alarm_message()    # 存告警记录
  └─ _handle_box_face_results()          # 人脸比对 + 分析入库
```

### 算法调度

`algorithm_runner` 为每个摄像头维护独立的算法实例链表：

```
摄像头 1 (vid_id=1)
  ├─ AlgorithmWrapper(code="face_detection", infer_interval=0.3s)
  ├─ AlgorithmWrapper(code="arcface_recognition", infer_interval=2.0s)
  └─ AlgorithmWrapper(code="realtime_face_analysis", infer_interval=0.1s)

摄像头 2 (vid_id=2)
  └─ AlgorithmWrapper(code="face_detection", infer_interval=0.3s)
```

- 每个插件实例独立，互不共享状态
- `infer_interval` 控制推理频率，避免 NPU 过载
- 插件接口：`infer(frame: np.ndarray) -> dict | None`

## 部署

### 环境要求

- 华为 Ascend 310 / 710 NPU
- CANN 已安装（提供 `acl` Python 模块）
- Python 3.9+
- ffmpeg

### 1. 验证 CANN 环境

```bash
npu-smi info
python3 -c "import acl; print('CANN OK')"
```

### 2. 模型转换（在开发机上执行一次）

```bash
# 人脸检测 (Caffe → OM)
atc --model=deploy.prototxt --weight=res10_300x300_ssd_iter_140000.caffemodel \
    --framework=0 --output=face_detection.om --soc_version=Ascend310B4 \
    --input_shape="data:1,3,300,300" --input_format=NCHW

# 人脸特征提取 (ONNX → OM)
atc --model=w600k_r50.onnx --framework=5 --output=arcface.om \
    --soc_version=Ascend310B4
```

### 3. 部署文件到盒子

```bash
# 拷贝模型
scp face_detection.om arcface.om user@box:~/binhua_box/weights/

# 拷贝代码
rsync -av --exclude='__pycache__' --exclude='weights/*.caffemodel' \
      --exclude='weights/*.prototxt' --exclude='weights/*.onnx' \
      ./binhua_box/ user@box:~/binhua_box/
```

### 4. 配置环境变量

```bash
# box.env
BOX_SERIAL=0004
BOX_NAME=box_0004
RABBITMQ_HOST=192.168.0.246
RABBITMQ_PORT=5672
RABBITMQ_USER=hhx
RABBITMQ_PASSWORD=hhx4201!
RABBITMQ_VHOST=/
SRS_RTMP_HOST=192.168.0.246
SRS_RTMP_PORT=1935
MAX_CONCURRENT_CAMERAS=8
```

### 5. 安装依赖并启动

```bash
cd ~/binhua_box
pip3 install -r requirements.txt

# 方式一：直接启动
set -a && source box.env && set +a
python3 -m box.main

# 方式二：使用启动脚本
chmod +x start_box.sh
./start_box.sh
```

启动成功日志：

```
[box] box_0004 (serial=0004) connected to RabbitMQ
[box] listening on routing key: algorithm_0004
[box] capabilities: ['face_detection', 'arcface_recognition', 'realtime_face_analysis']
[box] local API at http://0.0.0.0:9100
```

## 触发检测

### 手动触发

前端监控页面点击"启动"按钮，或调用后端 API：

```bash
curl -X POST http://<backend>:9099/dev-api/xuzhou/command/push_video_config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"vid_id": 1}'
```

后端会将摄像头配置和算法列表通过 RabbitMQ 推送到盒子。

### 定时触发

在后端 `系统管理 → 定时任务` 中为摄像头配置 cron 表达式：
- 调用目标：`module_task.video_ai.run`
- 参数：`{"video_id": "1"}`

后台 `InferenceMonitor` 每 5 分钟检查一次，确保应运行的摄像头在运行，不应运行的已停止。

## 本地 API

盒子启动后在 9100 端口提供 HTTP 接口：

| 端点 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /cameras` | 当前运行的摄像头列表 |
| `GET /cameras/{vid_id}/status` | 指定摄像头状态 |
| `GET /cameras/{vid_id}/snapshot` | 摄像头实时快照 (JPEG) |
| `GET /cameras/{vid_id}/stream` | 摄像头 MJPEG 实时流 |
| `GET /algorithms` | 已加载的算法列表 |

## 算法插件开发

插件文件放在 `algorithms/` 目录下，文件名即算法 code。

```python
# algorithms/my_algorithm.py
class Algorithm:
    def __init__(self, params: dict):
        # params 来自后端算法配置
        self.threshold = float(params.get("threshold", 0.5))

    def infer(self, frame: np.ndarray):
        # frame: BGR numpy array
        # 返回 dict 上报给后端，返回 None 表示本帧无结果
        result = do_inference(frame)
        if result:
            return {"detections": result, "count": len(result)}
        return None
```

插件放到 `algorithms/` 目录后重启盒子即可自动发现，无需改任何其他代码。

## 监控与排查

### 查看盒子日志

```bash
# 实时日志
journalctl -u binhua_box -f

# 或直接看 stdout
python3 -m box.main
```

### 检查 NPU 使用

```bash
npu-smi info watch
```

### 检查 RabbitMQ 连接

```bash
# 查看盒子监听的队列
rabbitmqctl list_queues | grep algorithm_0004

# 查看消息堆积
rabbitmqctl list_queues name messages consumers
```

### 常见问题

**Q: 启动报 `acl.init failed`**

检查 CANN 是否正确安装，`npu-smi info` 能否看到 NPU 设备。

**Q: 模型加载失败 `Failed to load model`**

确认 `weights/face_detection.om` 和 `weights/arcface.om` 存在，且 `--soc_version` 与盒子 NPU 型号匹配。

**Q: 算法不触发**

- 检查后端日志，确认 `push_video_config` 是否成功推送到 RabbitMQ
- 检查摄像头 `vidAlgorithm` 是否配置了算法
- 检查摄像头 `vidBoxSerial` 是否与 `BOX_SERIAL` 一致

**Q: 前端观看卡顿**

- 确认 ffmpeg 使用了 `-c copy`（RTSP 摄像头），不占用 CPU
- 检查盒子到 SRS 的网络带宽（单路 RTMP 约 2-4 Mbps）
- 如为 USB 摄像头，ffmpeg 需要 x264 编码，可增加 `-threads 2` 限制线程数

## 配置参考

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BOX_SERIAL` | `0004` | 盒子序列号，对应后端 routing key |
| `BOX_NAME` | `box_0004` | 盒子名称 |
| `RABBITMQ_HOST` | `192.168.0.246` | RabbitMQ 地址 |
| `RABBITMQ_PORT` | `5672` | RabbitMQ 端口 |
| `SRS_RTMP_HOST` | `127.0.0.1` | SRS 服务器地址 |
| `SRS_RTMP_PORT` | `1935` | SRS RTMP 端口 |
| `MAX_CONCURRENT_CAMERAS` | `8` | 最大并发摄像头数 |
| `ASCEND_DEVICE_ID` | `0` | NPU 设备 ID |
| `DEVICE_STATUS_INTERVAL` | `3` | 设备状态上报间隔（秒） |
