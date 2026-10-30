"""A real JPEG/heartbeat client for LAN gateways, not a synthetic device simulator.

Usage: python network_client.py --config private-device.json --jpeg captured.jpg
The JSON is copied from the workbench's network enrollment panel.
"""
import argparse
import json
from pathlib import Path
import httpx

def send(config, image=None):
    for field in ('server_url','device_key','hardware_id'):
        if not config.get(field):raise ValueError('Device configuration is missing '+field)
    if not config['server_url'].startswith(('http://','https://')):raise ValueError('Server URL must use HTTP or HTTPS')
    headers={'Authorization':'Bearer '+config['device_key'],'Device-Id':config['hardware_id']}
    with httpx.Client(base_url=config['server_url'].rstrip('/'),headers=headers,timeout=20,trust_env=False) as client:
        heartbeat=client.post('/api/device/heartbeat');heartbeat.raise_for_status()
        if image is None:return heartbeat.json()
        raw=Path(image).read_bytes()
        if not raw.startswith(b'\xff\xd8'):raise ValueError('Capture must be a real JPEG file')
        response=client.post('/api/device/frame',content=raw,headers={'Content-Type':'image/jpeg'});response.raise_for_status()
        return response.json()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,help='Private JSON enrollment configuration')
    parser.add_argument('--jpeg',help='A JPEG captured by your gateway camera')
    args=parser.parse_args()
    try:
        result=send(json.loads(Path(args.config).read_text(encoding='utf-8-sig')),args.jpeg)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,OSError,httpx.HTTPError):
        raise SystemExit('连接或上传失败。请检查服务地址、设备密钥、真实 MAC 和局域网连通性。')
