import re

from app.analysis import analysis_schema
from app.core.models import AnalysisResult


def test_legacy_columns_are_added_idempotently(monkeypatch):
    """遗留列与列注释都应被补齐，并且第二次执行不再产生任何 ALTER。"""
    # 模拟早期版本的库：既缺 vibraimage 列，也缺后加的 evidence_json
    existing = {c.name for c in AnalysisResult.__table__.columns} - {'e1_aggression', 'evidence_json'}
    comments = {}
    calls = []

    class Cursor:
        def __init__(self):
            self.last = ''
            self.rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def fetchall(self):
            # 注释查询与列查询走的都是 information_schema，按最后一条 SQL 区分
            if 'information_schema.COLUMNS' in self.last:
                return [{'COLUMN_NAME': n, 'COLUMN_COMMENT': comments.get(n, '')} for n in existing]
            return [{'Field': name} for name in existing]

        def execute(self, sql, args=None):
            self.last = sql
            self.rowcount = 0
            calls.append(sql)
            added = re.search(r'ADD COLUMN `([a-z0-9_]+)`', sql)
            if added:
                assert added.group(1) not in existing, 'Duplicate ADD COLUMN'
                existing.add(added.group(1))
            m = re.match(r'ALTER TABLE `analysis_results` MODIFY COLUMN `([a-z0-9_]+)` .* COMMENT %s$', sql)
            if m and args:
                comments[m.group(1)] = args[0]

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(analysis_schema, 'get_connection', Connection)

    analysis_schema.ensure_schema()
    assert any('ADD COLUMN `e1_aggression` FLOAT' in s for s in calls)
    assert any(re.search(r'ADD COLUMN `?evidence_json`?', s) for s in calls)
    assert any('COMMENT %s' in s for s in calls), '列注释应被补齐'
    assert comments.get('learning_state'), 'learning_state 应写入注释'
    assert comments.get('evidence_json'), 'evidence_json 应写入注释'

    calls.clear()
    analysis_schema.ensure_schema()
    assert not any('ALTER TABLE' in s for s in calls), '第二次执行不应再做任何改动'
