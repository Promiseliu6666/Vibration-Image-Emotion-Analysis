"""Analysis capabilities and durable assignments for the shared camera catalog."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from hik_vision.camera_contract import parse_camera_id


ALGORITHMS = [
    {
        'id': 'vibration', 'name': '幸福指数 / 振动情绪分析', 'selectable': True,
        'description': '通过面部微振动计算 e1–e14，并汇总幸福指数与安全风险。',
        'scenes': ['心理状态观察', '员工健康观察', '门岗'],
        'sources': ['local', 'rtsp', 'xiaozhi'],
        'metrics': [
            {'key': 'happiness_index', 'label': '幸福指数'},
            {'key': 'safety_risk_level', 'label': '安全风险'},
            {'key': 'e1-e14', 'label': '振动心理指标 e1–e14'},
        ],
    },
    {
        'id': 'fatigue', 'name': '疲劳检测', 'selectable': True,
        'description': '根据眼口状态和姿态时序计算疲劳趋势，默认展示无检测线框的原始画面。',
        'scenes': ['疲劳行为观察', '值班室', '操作岗位'],
        'sources': ['local', 'rtsp', 'xiaozhi'],
        'metrics': [
            {'key': 'fatigue_score', 'label': '疲劳度'},
            {'key': 'blink_total', 'label': '眨眼次数'},
            {'key': 'yawn_total', 'label': '哈欠次数'},
            {'key': 'last_step.features.perclos', 'label': '闭眼比例'},
            {'key': 'last_step.features.head_pitch', 'label': '头部俯仰'},
            {'key': 'last_step.features.head_roll', 'label': '头部侧倾'},
        ],
    },
    {
        'id': 'face_detection', 'name': '人脸检测', 'selectable': False,
        'description': 'OpenCV SSD 人脸定位，作为振动分析的前置步骤运行。',
        'scenes': [], 'sources': ['local', 'rtsp', 'xiaozhi'],
        'metrics': [{'key': 'face_detected', 'label': '人脸状态'}],
    },
    {
        'id': 'face_stability', 'name': '人脸稳定检测', 'selectable': False,
        'description': '连续确认人脸位置稳定后触发振动分析。',
        'scenes': [], 'sources': ['local', 'rtsp', 'xiaozhi'],
        'metrics': [{'key': 'stability_progress', 'label': '稳定确认进度'}],
    },
    {
        'id': 'face_identity', 'name': '人员身份识别', 'selectable': False,
        'description': 'PP-YOLOE + ResNet50 人脸比对，与振动分析联动显示登记人员信息。',
        'scenes': [], 'sources': ['local', 'rtsp', 'xiaozhi'],
        'metrics': [{'key': 'person', 'label': '人员信息与匹配相似度'}],
    },
]


def normalize_algorithms(value):
    values = [value] if isinstance(value, str) else value
    selectable = {a['id'] for a in ALGORITHMS if a['selectable']}
    if (not isinstance(values, list) or not values
            or any(not isinstance(item, str) or item not in selectable for item in values)):
        raise ValueError('请至少选择一种已接入的分析算法')
    return list(dict.fromkeys(values))


class CameraAlgorithmStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def _read(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('摄像头算法配置文件格式错误')
        for camera_id, config in data.items():
            parse_camera_id(camera_id)
            if (not isinstance(config, dict)
                    or not isinstance(config.get('scene'), str)
                    or not 1 <= len(config['scene'].strip()) <= 80
                    or type(config.get('show_overlay')) is not bool):
                raise ValueError('摄像头算法配置文件格式错误')
            algorithms = normalize_algorithms(config.get('algorithm_ids', config.get('algorithm_id')))
            config['algorithm_ids'] = algorithms
            config['algorithm_id'] = algorithms[0]
        return data

    def get(self, camera_id: str) -> dict:
        camera_id = parse_camera_id(camera_id).camera_id
        with self.lock:
            return dict(self._read().get(camera_id, {
                'algorithm_id': 'vibration', 'scene': '心理状态观察',
                'algorithm_ids': ['vibration'],
                'show_overlay': False,
            }))

    def save(self, camera_id: str, algorithm_id: str | list[str], scene: str, show_overlay: bool) -> dict:
        camera_id = parse_camera_id(camera_id).camera_id
        algorithms = normalize_algorithms(algorithm_id)
        scene = scene.strip()
        if not scene or len(scene) > 80:
            raise ValueError('应用场景须为 1–80 个字符')
        config = {'algorithm_id': algorithms[0], 'algorithm_ids': algorithms, 'scene': scene,
                  'show_overlay': bool(show_overlay)}
        with self.lock:
            data = self._read()
            data[camera_id] = config
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as output:
                    json.dump(data, output, ensure_ascii=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return dict(config)


camera_algorithm_store = CameraAlgorithmStore(
    Path(__file__).resolve().parents[2] / '.runtime' / 'camera-algorithms.json'
)
