"""Bounded record queries, using the workspace's China calendar consistently."""
from datetime import date, datetime, timedelta, timezone

# The workspace uses today's China calendar (UTC+8), without a platform tzdata dependency.
SHANGHAI = timezone(timedelta(hours=8), 'Asia/Shanghai')


def session_candidates(device_id='', period='all', day=None, limit=50, now=None):
    conditions = ["EXISTS (SELECT 1 FROM analysis_results v WHERE v.session_id=sx.id "
                  "AND v.person_present=1 AND v.learning_state<>'absent')"]
    values = []
    if device_id:
        conditions.append('sx.device_id=%s')
        values.append(device_id)
    if day or period != 'all':
        today = (now or datetime.now(timezone.utc)).astimezone(SHANGHAI).date()
        anchor = date.fromisoformat(day) if isinstance(day, str) else day
        last = anchor or today
        first = last - timedelta(days=6) if not anchor and period == 'week' else last
        start = datetime.combine(first, datetime.min.time(), SHANGHAI)
        end = datetime.combine(last + timedelta(days=1), datetime.min.time(), SHANGHAI)
        conditions.extend(['sx.start_time>=%s', 'sx.start_time<%s'])
        values.extend([start.astimezone(timezone.utc).replace(tzinfo=None),
                       end.astimezone(timezone.utc).replace(tzinfo=None)])
    # Restrict the session set BEFORE joining its potentially large image history.
    sql = ('SELECT sx.id FROM sessions sx WHERE ' + ' AND '.join(conditions) +
           ' ORDER BY sx.start_time DESC,sx.id DESC LIMIT %s')
    values.append(limit)
    return sql, tuple(values)
