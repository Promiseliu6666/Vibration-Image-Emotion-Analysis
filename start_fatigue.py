"""Start the standalone fatigue service with the shared local camera key."""
from pathlib import Path
import os
import runpy
import sys


def main():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'ruoyi-fastapi-backend'))
    from hik_vision.camera_bridge_config import get_camera_bridge_key
    os.environ['CAMERA_BRIDGE_KEY'] = get_camera_bridge_key(root)
    bundle = root / 'fatigue_model_bundle'
    os.chdir(bundle)
    sys.path.insert(0, str(bundle))
    sys.argv = [str(bundle / 'platform_service.py'), *sys.argv[1:]]
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main()
