"""One-shot wireless setup for the SenseCAP Watcher study firmware.

Run it with the USB cable plugged in: it reads the device Wi-Fi MAC from the
console port, registers that physical device in the local database, generates
its device key, and pushes the upload target to the device, so no manual serial
terminal work is needed. After it reports success the cable can be removed.

网页上的"Wi-Fi 接入"按钮（POST /api/workspace/wireless-setup）走的是同一份实现
app/core/wireless_setup.py，两条路行为一致。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from app.core import wireless_setup
    try:
        result = wireless_setup.provision()
    except RuntimeError as error:
        raise SystemExit(str(error))
    for line in result['log']:
        print('  ' + line)
    status = result.get('status') or ''
    lines = [line.strip() for line in status.splitlines() if 'study_lan' in line]
    if lines:
        print('\n设备状态：')
        for line in lines:
            print('  ' + line)
    print(f"\n完成。设备 {result['device_id']} 会继续通过 Wi-Fi 上传画面，现在可以拔掉 USB 线。")
    print('提示：如果电脑换了网络导致地址变化，插回线重跑本脚本即可。')


if __name__ == '__main__':
    main()
