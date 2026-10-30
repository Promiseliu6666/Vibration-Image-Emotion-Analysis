"""观察时段到点的设备语音提醒。

用户设定一段观察时间，期间照常采集分析；时间到（或页面已关闭）时由这里调用小智语音，
提示起身活动、远眺休息。提醒与用户后续的"我已休息活动 / 稍后提醒"自报反馈构成闭环。
"""
import asyncio
from app.analysis.phone_alerts import play_usb
from app.core.db import get_connection

POLL_SECONDS = 10
VOICE_COMMAND = 'study_eye_alert'
VOICE_ACK = 'study_eye_ack'


def due(limit=8):
    """已到截止时间、还没提醒过的观察时段。"""
    c = get_connection()
    try:
        with c.cursor() as q:
            q.execute("SELECT id,device_id FROM observation_windows WHERE status='running' "
                      "AND started_at+INTERVAL minutes MINUTE<=UTC_TIMESTAMP() ORDER BY id LIMIT %s", (limit,))
            return q.fetchall()
    finally:
        c.close()


def claim(ident):
    """把时段从 running 改成 reminding，避免重复或并发投递。"""
    c = get_connection()
    try:
        with c.cursor() as q:
            q.execute("UPDATE observation_windows SET status='reminding' WHERE id=%s AND status='running'", (ident,))
            changed = q.rowcount
        c.commit()
        return bool(changed)
    finally:
        c.close()


def finish(ident, status, error=None):
    c = get_connection()
    try:
        with c.cursor() as q:
            q.execute("UPDATE observation_windows SET status='done',ended_at=UTC_TIMESTAMP(),"
                      "reminded_at=UTC_TIMESTAMP(),remind_status=%s,remind_error=%s WHERE id=%s AND status='reminding'",
                      (status, (error or '')[:160] or None, ident))
        c.commit()
    finally:
        c.close()


async def run():
    while True:
        try:
            for row in await asyncio.to_thread(due):
                if not await asyncio.to_thread(claim, row['id']):
                    continue
                try:
                    status, error = await asyncio.to_thread(play_usb, row['device_id'], VOICE_COMMAND, VOICE_ACK)
                except Exception as exc:  # 设备未连接、串口异常都不应影响服务
                    status, error = 'failed', str(exc)
                await asyncio.to_thread(finish, row['id'], status, error)
        except Exception:
            pass  # 数据库短暂不可用时继续轮询
        await asyncio.sleep(POLL_SECONDS)
