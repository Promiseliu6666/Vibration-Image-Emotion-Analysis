"""项目根目录与常用目录常量。

所有模块统一从这里取路径，不再用 __file__ 猜自己在哪一层 ——
这样文件在包内怎么移动都不会改坏运行时路径。
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / '.runtime'
FRAMES_DIR = PROJECT_ROOT / 'frames'
MODELS_DIR = PROJECT_ROOT / 'models'
STATIC_DIR = PROJECT_ROOT / 'static'
DOCS_DIR = PROJECT_ROOT / 'docs'
