"""Sample-based eye and posture reports. Unknown observations are never normal samples."""
import json, calendar, math
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from app.api.api_router import require_admin
from app.core.db import get_connection
from pymysql.cursors import SSDictCursor
router = APIRouter(prefix='/api/wellbeing')

def bounds(period, anchor):
    try:
        day = datetime.strptime(anchor, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(422, '请选择有效日期')
    if not 2000 <= day.year <= 2099:
        raise HTTPException(422, '请选择2000至2099年之间的日期')
    if period == 'week':
        start = day-timedelta(days=day.weekday()); end = start+timedelta(days=7)
    else:
        start = day.replace(day=1); end = start+timedelta(days=calendar.monthrange(day.year,day.month)[1])
    if start > datetime.utcnow()+timedelta(hours=8): raise HTTPException(422,'不能查看未来报告')
    return start-timedelta(hours=8), end-timedelta(hours=8)

def safe_seconds(value):
    """Ignore corrupt legacy durations without failing a whole report."""
    try:
        seconds = float(value or 0)
        return max(0, seconds) if math.isfinite(seconds) else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def comparison_bounds(start, end, period, now=None):
    """Compare equal elapsed portions, including partial current periods."""
    now = now or datetime.utcnow()
    if period == 'week':
        previous_start = start - timedelta(days=7)
        previous_end = start
    else:
        local_start = start + timedelta(hours=8)
        last_month = local_start - timedelta(days=1)
        previous_start = last_month.replace(day=1) - timedelta(hours=8)
        previous_end = start
    elapsed = max(timedelta(), min(now, end) - start)
    return previous_start, min(previous_end, previous_start + elapsed)


def change(current, previous):
    if current is None or previous is None:
        return None
    return round(current - previous, 1)


def summarize(rows, start=None):
    days={}; screen=pose=tilts=eligible=eyes=0; longest=0; longest_presence=0
    for row in rows:
        try:
            evidence=row.get('evidence_json') or '{}'
            o=(json.loads(evidence) if isinstance(evidence,str) else evidence).get('observations') or {}
        except (ValueError,TypeError,AttributeError): continue
        if not isinstance(o, dict) or 'screen_activity' not in o: continue
        if not isinstance(row.get('timestamp'), datetime): continue
        key=(row['timestamp']+timedelta(hours=8)).strftime('%m-%d')
        d=days.setdefault(key,dict(samples=0,eyes=0,screen=0,posture=0,tilted=0))
        eligible+=1; d['samples']+=1
        if o.get('eye_assessable'):
            eyes+=1;d['eyes']+=1
            if o.get('screen_activity'): screen+=1;d['screen']+=1
        if o.get('posture_assessable'):
            pose+=1;d['posture']+=1
            if o.get('posture_tilt'): tilts+=1;d['tilted']+=1
        duration=safe_seconds(o.get('screen_seconds'))
        if start is not None:duration=min(duration,max(0,(row['timestamp']-start).total_seconds()))
        longest=max(longest,duration)
        presence=safe_seconds(o.get('presence_seconds'))
        if start is not None:presence=min(presence,max(0,(row['timestamp']-start).total_seconds()))
        longest_presence=max(longest_presence,presence)
    return dict(samples=eligible,eye_samples=eyes,screen_samples=screen,posture_samples=pose,tilted_samples=tilts,
        screen_pct=round(100*screen/eyes,1) if eyes else None,
        tilted_pct=round(100*tilts/pose,1) if pose else None,longest_screen_minutes=round(longest/60,1),longest_presence_minutes=round(longest_presence/60,1),
        days=[dict(date=k,**v) for k,v in sorted(days.items())],
        scope='仅统计新版功能启用后的分析样本；样本占比不是全天时长。连续在位是有人出现的采样片段，不等于久坐时长。坐姿仅观察肩部持续倾斜，摄像头角度可能影响结果，不诊断眼病或脊柱疾病。',
        eye_plan=('连续屏幕相关活动超过20分钟的片段已出现，下一阶段先试着把休息安排在连续使用20分钟前。' if longest>=1200 else '下一阶段保持规律的用眼休息，学习间隙看看远处；留意眼睛是否干涩或不适，按自己的感受及时休息。'),
        posture_plan=('已观察到较多持续肩部倾斜的片段，下一阶段可以留意是否习惯偏向一侧；坐下时放松肩膀、双脚踩稳，学习间隙起身走动，避免长时间保持同一姿势。' if pose and tilts/pose>=.2 else '下一阶段养成经常变换姿势的习惯，学习间隙起身走动；每次坐下时留意肩膀是否放松、双脚是否踩稳，不必刻意长时间保持僵硬的坐姿。'),
        eye_advice='每使用屏幕约20分钟，看看约6米外的物体至少20秒；适当眨眼，避免长时间连续盯着屏幕，按自身感受安排休息。',
        posture_advice='让双脚自然踩稳，肩膀保持放松，避免长时间保持同一姿势。长时间保持不舒服姿势可能增加颈背不适，定期活动比追求固定姿势更重要。')

@router.get('/report')
def report(device_id:str,period:Literal['week','month']='week',anchor:str='',username=Depends(require_admin)):
    start,end=bounds(period,anchor or (datetime.utcnow()+timedelta(hours=8)).strftime('%Y-%m-%d'))
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT device_id,name FROM devices WHERE device_id=%s',(device_id,));device=q.fetchone()
            if not device:raise HTTPException(404,'设备不存在')
        # Both histories are streamed; only compact daily totals stay in memory.
        def read_period(begin, finish):
            with c.cursor(SSDictCursor) as q:
                q.execute('SELECT a.timestamp,a.evidence_json FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s AND a.person_present=1 AND a.timestamp>=%s AND a.timestamp<%s ORDER BY a.timestamp',(device_id,begin,finish))
                return summarize(iter(q),begin)
        observed_end = min(end, datetime.utcnow())
        result=read_period(start,observed_end)
        previous_start,previous_end=comparison_bounds(start,end,period,observed_end)
        previous=read_period(previous_start,previous_end)
        result['comparison'] = dict(
            start=(previous_start+timedelta(hours=8)).isoformat(timespec='minutes'),
            end=(previous_end+timedelta(hours=8)).isoformat(timespec='minutes'),
            samples=previous['samples'],
            screen_pct=previous['screen_pct'],tilted_pct=previous['tilted_pct'],
            screen_change=change(result['screen_pct'],previous['screen_pct']),
            tilted_change=change(result['tilted_pct'],previous['tilted_pct']))
        with c.cursor() as q:
            q.execute("SELECT DATE(created_at+INTERVAL 8 HOUR) AS day,kind,COUNT(*) AS n FROM health_actions WHERE username=%s AND device_id=%s AND response='done' AND created_at>=%s AND created_at<%s GROUP BY day,kind ORDER BY day",(username,device_id,start,observed_end))
            actions=q.fetchall()
        result['self_reported_actions'] = [dict(date=str(a['day']),kind=a['kind'],count=int(a['n'])) for a in actions]
        result['active_days'] = len(result['days'])
        result['observed_through']=(observed_end+timedelta(hours=8)).isoformat(timespec='minutes')
        result.update(device=device,period=period,start=(start+timedelta(hours=8)).strftime('%Y-%m-%d'),end=(end+timedelta(hours=8)-timedelta(days=1)).strftime('%Y-%m-%d'))
        return result
    finally:c.close()
