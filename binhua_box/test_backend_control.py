"""
End-to-end test: control cameras via backend API → RabbitMQ → box.

Usage (any machine that can reach the backend):
    cd box
    python test_backend_control.py --backend http://127.0.0.1:9099

    # Start camera vid_id=4
    python test_backend_control.py --backend http://127.0.0.1:9099 --start 4

    # Stop camera
    python test_backend_control.py --backend http://127.0.0.1:9099 --stop 4

    # Check device status
    python test_backend_control.py --backend http://127.0.0.1:9099 --status 4

    # List all cameras
    python test_backend_control.py --backend http://127.0.0.1:9099 --list

    # List online boxes
    python test_backend_control.py --backend http://127.0.0.1:9099 --boxes
"""
import argparse
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class BackendClient:
    """Minimal HTTP client for the backend API."""

    def __init__(self, base_url: str, username: str = "admin", password: str = "admin123"):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            return json.loads(e.read().decode())
        except URLError as e:
            return {"code": 500, "msg": f"Connection failed: {e.reason}"}

    def login(self) -> bool:
        resp = self._request("POST", "/login", {"username": self.username, "password": self.password})
        self._token = resp.get("token") or (resp.get("data", {}).get("token"))
        if self._token:
            print(f"[login] ✓ token={self._token[:20]}...")
            return True
        print(f"[login] ✗ {resp.get('msg', resp)}")
        return False

    def list_cameras(self) -> list[dict]:
        resp = self._request("GET", "/xuzhou/video/list?pageNum=1&pageSize=200")
        rows = resp.get("rows") or resp.get("data", {}).get("rows", [])
        return rows

    def start_camera(self, vid_id: int) -> dict:
        return self._request("POST", "/xuzhou/command/push_video_config", {"vid_id": vid_id})

    def stop_camera(self, vid_id: int) -> dict:
        return self._request("POST", "/xuzhou/command/push_video_config", {"vid_id": vid_id, "action": "stop"})

    def device_status(self, vid_id: int | None = None) -> dict:
        path = f"/xuzhou/command/device_status?vid_id={vid_id}" if vid_id else "/xuzhou/command/device_status"
        return self._request("GET", path)

    def list_boxes(self) -> dict:
        return self._request("GET", "/xuzhou/command/boxes")


def fmt_status(status: str) -> str:
    icons = {"running": "🟢", "stopped": "⚪", "error": "🔴", "offline": "🟠", "unknown": "⚪"}
    return f"{icons.get(status, '❓')} {status}"


def cmd_list(client: BackendClient) -> None:
    cameras = client.list_cameras()
    if not cameras:
        print("No cameras found")
        return

    running = sum(1 for c in cameras if c.get("isRunning"))
    print(f"\n{'id':>4}  {'name':<16} {'serial':<12} {'type':<6} {'box':<6} {'status':>10}  error")
    print("-" * 90)
    for c in cameras:
        vid_id = c.get("vidId", "")
        name = (c.get("vidName") or "")[:16]
        serial = (c.get("vidSerial") or "")[:12]
        vtype = c.get("vidType", "")
        box = (c.get("vidBoxSerial") or "-")[:6]
        status = fmt_status(c.get("deviceStatus", "unknown"))
        error = (c.get("deviceErrorMessage") or "")[:40]
        print(f"{vid_id:>4}  {name:<16} {serial:<12} {vtype:<6} {box:<6} {status:>10}  {error}")
    print(f"\n{len(cameras)} cameras | {running} running")


def cmd_start(client: BackendClient, vid_id: int) -> None:
    print(f"\n[start] sending start command for vid_id={vid_id}...")
    resp = client.start_camera(vid_id)
    if resp.get("code") == 200:
        data = resp.get("data", {})
        print(f"  ✓ action: {data.get('action')}")
        print(f"  ✓ srs_flv_url: {data.get('srsFlvUrl')}")
        runs = data.get("runs", [])
        if runs:
            print(f"  ✓ runs:")
            for r in runs:
                print(f"      vid_id={r.get('vidId')} algo={r.get('algorithmCode')} status={r.get('status')}")
        else:
            print(f"  (no algorithms — pure streaming mode)")
        print(f"\n  To view: use flv.js player with {data.get('srsFlvUrl')}")
    else:
        print(f"  ✗ {resp.get('msg', resp)}")

    time.sleep(2)
    status = client.device_status(vid_id)
    print(f"  device status: {json.dumps(status.get('data', {}), ensure_ascii=False)}")


def cmd_stop(client: BackendClient, vid_id: int) -> None:
    print(f"\n[stop] sending stop command for vid_id={vid_id}...")
    resp = client.stop_camera(vid_id)
    if resp.get("code") == 200:
        print(f"  ✓ stopped")
    else:
        print(f"  ✗ {resp.get('msg', resp)}")


def cmd_status(client: BackendClient, vid_id: int | None) -> None:
    resp = client.device_status(vid_id)
    data = resp.get("data", {})
    if vid_id:
        print(f"\n[status] vid_id={vid_id}: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"\n[status] all devices: {json.dumps(data, indent=2, ensure_ascii=False)}")


def cmd_boxes(client: BackendClient) -> None:
    resp = client.list_boxes()
    data = resp.get("data", {})
    online = data.get("online", [])
    offline = data.get("offline", [])
    print(f"\n[boxes] online: {data.get('online_count', 0)} | total: {data.get('total', 0)}")
    for b in online:
        caps = b.get("capabilities", [])
        print(f"  🟢 serial={b.get('serial')} name={b.get('box_name')} host={b.get('host')} caps={caps}")
    for b in offline:
        print(f"  ⚫ serial={b.get('serial')} name={b.get('box_name')} last_seen={b.get('last_seen')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test backend → box camera control")
    parser.add_argument("--backend", default="http://127.0.0.1:9099", help="Backend base URL")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--list", action="store_true", help="List all cameras")
    parser.add_argument("--start", type=int, metavar="VID_ID", help="Start camera by vid_id")
    parser.add_argument("--stop", type=int, metavar="VID_ID", help="Stop camera by vid_id")
    parser.add_argument("--status", type=int, const=None, nargs="?", metavar="VID_ID", help="Get device status (all or by vid_id)")
    parser.add_argument("--boxes", action="store_true", help="List online boxes")
    args = parser.parse_args()

    client = BackendClient(args.backend, args.username, args.password)

    if not client.login():
        sys.exit(1)

    if args.list:
        cmd_list(client)
    elif args.start:
        cmd_start(client, args.start)
    elif args.stop:
        cmd_stop(client, args.stop)
    elif hasattr(args, "status") and args.status is not None:
        cmd_status(client, args.status)
    elif args.boxes:
        cmd_boxes(client)
    else:
        # default: show cameras + boxes
        cmd_boxes(client)
        cmd_list(client)
        print("\nUse --start <vid_id> | --stop <vid_id> | --status | --boxes | --list")


if __name__ == "__main__":
    main()
