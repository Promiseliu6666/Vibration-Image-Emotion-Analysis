from app.core.db import get_connection
from app.analysis.analysis_columns import COLUMN_DDL


def ensure_comments(cur):
    """按需补齐列注释；注释一致时不做任何改动。"""
    cur.execute("""SELECT COLUMN_NAME, COLUMN_COMMENT FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='analysis_results'""")
    current = {r['COLUMN_NAME']: (r['COLUMN_COMMENT'] or '') for r in cur.fetchall()}
    changed = 0
    for name, (ddl, comment) in COLUMN_DDL.items():
        if name not in current:
            continue
        if current[name] == comment:
            continue
        cur.execute('ALTER TABLE `analysis_results` MODIFY COLUMN `' + name + '` ' + ddl + ' COMMENT %s', (comment,))
        changed += 1
    return changed


def ensure_schema():
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SHOW COLUMNS FROM analysis_results')
            existing={r['Field'] for r in cur.fetchall()}
            from app.core.models import AnalysisResult
            for column in AnalysisResult.__table__.columns:
                if column.name not in existing:
                    definition=str(column.type.compile(dialect=__import__('sqlalchemy').dialects.mysql.dialect()))
                    cur.execute(f'ALTER TABLE analysis_results ADD COLUMN `{column.name}` {definition} NULL')
                    existing.add(column.name)
            if 'evidence_json' not in existing:
                cur.execute('ALTER TABLE analysis_results ADD COLUMN evidence_json LONGTEXT NULL')
                existing.add('evidence_json')
            # COLUMN_DDL 是唯一事实来源：这里补齐它声明、但库里还没有的列
            # （例如风险标志位列），避免"加了定义却忘了建列"。
            for name, (ddl, comment) in COLUMN_DDL.items():
                if name not in existing:
                    cur.execute('ALTER TABLE `analysis_results` ADD COLUMN `' + name + '` ' + ddl + ' COMMENT %s', (comment,))
                    existing.add(name)
            ensure_comments(cur)
            _backfill_observations(cur)
        conn.commit()
    finally: conn.close()


# 观测值原本只存在 evidence_json 里，后来落成了列以便快速聚合。
# 不回填的话，切换存储方式后历史指标会突然全部变 0（看起来像数据丢了）。
# 幂等：以 near_work_seconds IS NULL 作为"尚未回填"的标记，完成后只是一次空扫描。
# 注意：observations 里的布尔量在 JSON 里是 true/false，不能直接 CAST 成整数；
# JSON 的 null 用 JSON_UNQUOTE 会变成字符串 'null'，要用 NULLIF 还原成 SQL NULL。
_BACKFILL_MAP = [
    ('near_work_seconds', "CAST(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.near_work_seconds') AS UNSIGNED)"),
    ('screen_seconds', "CAST(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.screen_seconds') AS UNSIGNED)"),
    ('presence_seconds', "CAST(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.presence_seconds') AS UNSIGNED)"),
    ('posture_assessable', "(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.posture_assessable')=TRUE)"),
    ('posture_tilt', "(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.posture_tilt')=TRUE)"),
    ('eye_assessable', "(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.eye_assessable')=TRUE)"),
    ('posture_reason', "NULLIF(JSON_UNQUOTE(JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.posture_reason')),'null')"),
]


def _backfill_observations(cur, limit=20000):
    """把 evidence_json 里的观测值回填到对应列；每次最多处理 limit 行。"""
    sets = ",".join(
        "`%s`=%s" % (col, expr) for col, expr in _BACKFILL_MAP)
    cur.execute(
        "UPDATE analysis_results SET " + sets +
        " WHERE near_work_seconds IS NULL AND evidence_json IS NOT NULL"
        " AND JSON_EXTRACT(IF(JSON_VALID(evidence_json),evidence_json,'{}'),'$.observations.near_work_seconds') IS NOT NULL"
        " LIMIT " + str(int(limit)))
    changed = cur.rowcount
    return changed
