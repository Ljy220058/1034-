from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.creative_idea_tags import (
    KanbanTaskRecord,
    duplicate_risk,
    extract_theme_tags,
    load_tasks_from_sqlite,
    render_markdown,
    summarize_tasks,
)


def test_extract_theme_tags_detects_running_campus_waterfall_and_import() -> None:
    text = '为校园跑团活动瀑布流添加跑步数据导入向导，展示跑量和配速预检结果'

    tags = extract_theme_tags(text)

    tag_names = {item['tag'] for item in tags}
    assert {'跑步数据', '校园风格', '瀑布流', '导入向导'} <= tag_names


def test_summarize_tasks_outputs_dedupe_rules_and_duplicate_groups() -> None:
    records = [
        KanbanTaskRecord(
            task_id='t_1',
            title='为跑步数据导入向导添加预检文案',
            body='输出 docs/import.md，覆盖 CSV 导入、错误文案和跑量字段。',
            assignee='backend-dev',
            status='done',
            workspace_path='/repo',
        ),
        KanbanTaskRecord(
            task_id='t_2',
            title='为跑步数据导入向导补充预检文案',
            body='输出 docs/import.md，覆盖 CSV 导入、错误文案和跑量字段。',
            assignee='backend-dev',
            status='running',
            workspace_path='/repo',
        ),
        KanbanTaskRecord(
            task_id='t_3',
            title='设计校园挑战赛排行榜文档',
            body='说明校园、排行榜、挑战赛和跑量统计。',
            assignee='docs-writer',
            status='done',
            workspace_path='/repo',
        ),
    ]

    report = summarize_tasks(records)

    assert report['summary']['total_tasks'] == 3
    assert report['summary']['status_counts']['running'] == 1
    assert report['dedupe_rules']
    assert report['duplicate_groups']
    assert report['duplicate_groups'][0]['count'] == 2
    assert any(item['tag'] == '导入向导' for item in report['summary']['top_themes'])


def test_duplicate_risk_flags_same_workspace_and_same_artifact() -> None:
    left = KanbanTaskRecord(
        task_id='t_1',
        title='整理创意任务去重策略',
        body='输出 docs/创意任务去重策略.md，说明重复和去重规则。',
        assignee='idea-scout',
        status='running',
        workspace_path='/repo',
    )
    right = KanbanTaskRecord(
        task_id='t_2',
        title='补充创意任务重复预警规则',
        body='更新 docs/创意任务去重策略.md，加入去重规则示例。',
        assignee='idea-scout',
        status='ready',
        workspace_path='/repo',
    )

    risk = duplicate_risk(left, right)

    assert risk['risk_level'] == '高'
    assert '目标产物路径相同' in risk['reasons']
    assert '工作区相同' in risk['reasons']


def test_load_tasks_from_sqlite_reads_recent_tasks(tmp_path: Path) -> None:
    db_path = tmp_path / 'kanban.db'
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            '''
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT,
                assignee TEXT,
                status TEXT NOT NULL,
                workspace_path TEXT,
                created_at INTEGER NOT NULL
            )
            '''
        )
        connection.execute(
            "INSERT INTO tasks VALUES ('t_1', '跑步数据导入向导', 'CSV 导入预检', 'backend-dev', 'done', '/repo', 2)"
        )
        connection.execute(
            "INSERT INTO tasks VALUES ('t_2', '校园瀑布流卡片', '活动列表卡片流', 'frontend-dev', 'running', '/repo', 3)"
        )

    records = load_tasks_from_sqlite(db_path, limit=1)

    assert len(records) == 1
    assert records[0].task_id == 't_2'
    assert records[0].title == '校园瀑布流卡片'


def test_render_markdown_contains_reusable_sections() -> None:
    report = summarize_tasks([
        KanbanTaskRecord(task_id='t_1', title='校园挑战赛排行榜', body='跑量 排行榜', status='done')
    ])

    markdown = render_markdown(json.loads(json.dumps(report, ensure_ascii=False)))

    assert '# 中文创意库标签摘要' in markdown
    assert '## 趋势标签' in markdown
    assert '## 去重规则' in markdown
    assert '## 下一轮创意使用方式' in markdown
    assert '## 本地运行示例' in markdown
    assert report['local_run_example']['json_output'] == 'docs/中文创意库标签摘要.json'
