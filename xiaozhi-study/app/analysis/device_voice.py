"""哪台设备的语音提醒由固件播报。

study_sync 的位标志下发成功后，固件自己决定播报哪一种本地中文提醒，
服务端就不再往同一个扬声器发 study_phone_alert / study_eye_alert。
老固件（没有 study_sync）保持原来的服务端播报，互不影响。
"""
from collections import OrderedDict


_devices = OrderedDict()


def mark(device, enabled):
    """记录这台物理设备的播报归属；由 state_sync 按固件回执更新。"""
    _devices[device] = bool(enabled)
    _devices.move_to_end(device)
    while len(_devices) > 64:
        _devices.popitem(last=False)
    return _devices[device]


def plays(device):
    """固件是否接管了这台设备的语音提醒（未见过回执时按服务端播报处理）。"""
    return bool(_devices.get(device))


def forget(device):
    _devices.pop(device, None)
