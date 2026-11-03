# FatigueSense 推理迁移包

这个文件夹是推理专用、可整体迁移的最小运行包。复制整个
`fatigue_model_bundle/` 后，无需原仓库里的 `runs/`、`data/`、训练脚本或
Notebook。

## 目录内容

```text
fatigue_model_bundle/
├── assets/
│   ├── best_eyes.pt
│   ├── best_mouth.pt
│   ├── best_pose_model.pt
│   ├── best_temporal.pt
│   ├── model_config.json
│   ├── normalization.json
│   └── face_landmarker.task
├── fatigue_pipeline/       # 人脸裁剪、眼睛/嘴部分类、姿态、特征聚合
├── model_architecture/     # CNN、BiGRU 结构和归一化加载器
├── scripts/
│   ├── live_inference_local.py
│   ├── pose_pipeline.py
│   ├── vision_pipeline.py
│   └── weights_path.py     # 所有资产路径统一在这里
├── verify_bundle.py
├── requirements.txt
└── LICENSE
```

四个 `.pt` 不能单独运行。`normalization.json`、`model_config.json` 和
`face_landmarker.task` 同样必须保留。

## 迁移方式

1. 将整个 `fatigue_model_bundle/` 复制到目标工程或目标磁盘。
2. 进入该文件夹：

   ```bash
   cd fatigue_model_bundle
   ```

3. 准备 Python 3.10+ 环境（推荐 3.11）并安装依赖：

   ```bash
   python -m pip install -r requirements.txt
   ```

   如果使用 CUDA，建议先按本机 CUDA 版本安装对应的 PyTorch，再安装其余依赖。

4. 运行自检。它会检查七个资产、JSON 内容，并实际加载眼睛、嘴部、姿态、
   BiGRU 和人脸关键点模型：

   ```bash
   python verify_bundle.py
   ```

   最后应看到：

   ```text
   [OK] All bundle models loaded successfully.
   ```

## 启动推理

所有命令都必须在本包根目录执行：

```bash
python -m scripts.vision_pipeline
python -m scripts.pose_pipeline
python -m scripts.live_inference_local
```

- `vision_pipeline`：只测试人脸关键点和眼睛/嘴部分类。
- `pose_pipeline`：只测试姿态模型。
- `live_inference_local`：完整流程，输出 0 到 1 的专注度分数。

完整流程默认需要约 90 秒预热：前 60 秒填充特征窗口，再累计 30 个 1 Hz
时序特征后才产生第一个分数。

摄像头编号、目标帧率和完整流程窗口参数可在对应脚本顶部修改：

```python
WEBCAM_INDEX = 0
TARGET_FPS = 30.0
DEMO_SUB_WINDOW_S = 60.0
DEMO_STEP_STRIDE_S = 1.0
WINDOW_STEPS = 30
```

## 集成到其他 Python 工程

把迁移包根目录加入 `PYTHONPATH`，或在包根目录运行程序。资产路径已根据
`scripts/weights_path.py` 所在位置动态解析，因此移动整个文件夹后无需修改
绝对路径。

```python
from fatigue_pipeline import FatiguePipeline
from scripts.weights_path import EYE_CKPT, LANDMARKER_PATH, MOUTH_CKPT

pipeline = FatiguePipeline(
    face_landmarker_path=LANDMARKER_PATH,
    eye_classifier_path=EYE_CKPT,
    mouth_classifier_path=MOUTH_CKPT,
    fps=30.0,
)

# frame 必须是 OpenCV BGR 图像。
probs = pipeline.process_frame(frame)
pipeline.close()
```

完整姿态、特征聚合和时序评分接线方式见
`scripts/live_inference_local.py`。训练、数据标注和评估功能不包含在此包中。
