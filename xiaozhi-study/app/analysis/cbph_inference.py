"""CBPH-Net 行为检测推理模块

使用 ONNX Runtime 加载 YOLOv8n 模型，检测学生课堂行为。
模型: STBD-08 数据集训练，8类 → 本项目使用7类；保留单人可观察的课堂行为。

类别映射:
    1: reading        → engaged_reading
    2: writing        → engaged_writing
    3: listening      → engaged_screen
    4: turning_around → distracted_away
"""

import numpy as np
from pathlib import Path
from threading import Lock

from app.core.paths import MODELS_DIR

# 模块级单例，进程启动时延迟加载
_model = None
_model_lock = Lock()

# 类别 ID → 名称映射（以模型内置类别元数据为准）
CLASS_MAP = {
    0: "hand_raising",
    5: "standing",
    6: "discussing",
    1: "reading",
    2: "writing",
    3: "listening",
    4: "turning_around",
}

# 推理支持举手、阅读、书写、听讲、转身、站立和讨论
TARGET_CLASSES = [0, 1, 2, 3, 4, 5, 6]

# 默认置信度阈值
DEFAULT_CONF = 0.5

# 模型文件路径（相对于项目根目录）
MODEL_PATH = MODELS_DIR / "cbph_best.onnx"

# 输入尺寸
INPUT_SIZE = (320, 320)


def get_model():
    """延迟加载 ONNX 模型（进程级单例，线程安全）"""
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            import onnxruntime as ort
            options=ort.SessionOptions()
            options.intra_op_num_threads=2
            options.inter_op_num_threads=1
            options.add_session_config_entry('session.intra_op.allow_spinning','0')
            options.add_session_config_entry('session.inter_op.allow_spinning','0')
            _model = ort.InferenceSession(str(MODEL_PATH),sess_options=options,providers=['CPUExecutionProvider'])
            print('[CBPH] ONNX Runtime 模型已加载')
    return _model


def infer(frame_bgr: np.ndarray, conf_threshold: float = DEFAULT_CONF) -> tuple:
    """CBPH-Net 学生行为推理

    Args:
        frame_bgr: BGR 格式图像 (H, W, 3)，任意尺寸
        conf_threshold: 置信度阈值，默认 0.4

    Returns:
        (action_name, confidence)
        - action_name: "reading" | "writing" | "listening" | "turning_around" | None
        - confidence: float (0.0 ~ 1.0)，无检测时为 0.0
    """
    model = get_model()

    # ultralytics YOLO 模式
    if hasattr(model, 'predict') or hasattr(model, '__call__'):
        results = model(
            frame_bgr,
            imgsz=INPUT_SIZE,
            classes=TARGET_CLASSES,
            conf=conf_threshold,
            verbose=False,
        )
        # 取置信度最高的检测结果
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            # 按置信度降序排列
            confs = boxes.conf.cpu().numpy()
            best_idx = int(confs.argmax())
            cls_id = int(boxes.cls[best_idx])
            conf = float(confs[best_idx])
            action = CLASS_MAP.get(cls_id)
            if action is not None:
                return action, conf
        return None, 0.0

    # 纯 onnxruntime 回退模式
    return _infer_ort(model, frame_bgr, conf_threshold)


def _infer_ort(session, frame_bgr: np.ndarray, conf_threshold: float) -> tuple:
    """纯 onnxruntime 推理（备选，无需 ultralytics/torch）"""
    import cv2

    h, w = frame_bgr.shape[:2]
    target_h, target_w = INPUT_SIZE

    # ---- 预处理 ----
    # letterbox resize + pad
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame_bgr, (new_w, new_h))
    canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    pad_y = (target_h - new_h) // 2
    pad_x = (target_w - new_w) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    # BGR→RGB, HWC→CHW, uint8→float32, /255
    img = canvas[..., ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    img = img[np.newaxis, ...]

    # ---- 推理 ----
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: img})[0]  # (1, 12, 2100)

    # ---- 后处理 ----
    # YOLOv8 ONNX output: (1, 4+nc, num_preds)
    # channels 0:3 = bbox [cx,cy,w,h], channels 4:11 = class_scores
    output = output[0]  # (12, 2100)
    bbox_raw = output[:4, :]  # (4, 2100)
    cls_raw = output[4:, :]   # (8, 2100)

    # Ultralytics export already decodes xywh in input pixels. Never decode twice.
    all_boxes, all_confs, all_cls_ids = [], [], []
    best_classes = cls_raw.argmax(axis=0)
    top_two = np.partition(cls_raw, -2, axis=0)[-2:]
    margin = top_two[-1] - top_two[-2]
    for cls_id in TARGET_CLASSES:
        scores = cls_raw[cls_id]
        mask = (scores > conf_threshold) & (best_classes == cls_id) & (margin >= .1)
        for index in np.flatnonzero(mask):
            cx, cy, bw, bh = bbox_raw[:, index]
            if not np.isfinite([cx,cy,bw,bh]).all() or bw <= 0 or bh <= 0:
                continue
            all_boxes.append((cx-bw/2, cy-bh/2, cx+bw/2, cy+bh/2))
            all_confs.append(float(scores[index]))
            all_cls_ids.append(cls_id)

    if not all_boxes:
        return None, 0.0

    # NMS
    boxes_np = np.array(all_boxes, dtype=np.float32)
    confs_np = np.array(all_confs, dtype=np.float32)

    # 还原到原图坐标 (letterbox 逆变换)
    boxes_np[:, [0, 2]] -= pad_x
    boxes_np[:, [1, 3]] -= pad_y
    boxes_np /= scale

    # 裁剪到图像范围
    boxes_np[:, [0, 2]] = boxes_np[:, [0, 2]].clip(0, w)
    boxes_np[:, [1, 3]] = boxes_np[:, [1, 3]].clip(0, h)

    indices = cv2.dnn.NMSBoxes(
        np.column_stack((boxes_np[:,0], boxes_np[:,1], boxes_np[:,2]-boxes_np[:,0], boxes_np[:,3]-boxes_np[:,1])).tolist(), confs_np.tolist(),
        conf_threshold, 0.45,
    )

    if len(indices) == 0:
        return None, 0.0

    # 取 NMS 后置信度最高的
    best_i = indices.flatten()[confs_np[indices.flatten()].argmax()]
    best_cls = int(all_cls_ids[best_i])
    best_conf = float(confs_np[best_i])
    action = CLASS_MAP.get(best_cls)

    return action, best_conf


def model_ready() -> bool:
    """检查模型文件是否存在"""
    return MODEL_PATH.exists()
