from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.creative_idea_tags import load_tasks_from_sqlite, render_markdown, summarize_tasks


def main() -> int:
    """生成中文创意任务标签摘要和去重规则报告。"""
    parser = argparse.ArgumentParser(description='生成中文创意库标签摘要')
    parser.add_argument('--db', default=os.getenv('HERMES_KANBAN_DB'), help='Hermes Kanban SQLite 路径')
    parser.add_argument('--limit', type=int, default=200, help='扫描最近任务数量')
    parser.add_argument('--json-out', default='docs/中文创意库标签摘要.json', help='JSON 输出路径')
    parser.add_argument('--md-out', default='docs/中文创意库标签摘要.md', help='Markdown 输出路径')
    args = parser.parse_args()

    if not args.db:
        parser.error('请通过 --db 或 HERMES_KANBAN_DB 指定看板数据库路径')

    records = load_tasks_from_sqlite(args.db, limit=args.limit)
    report = summarize_tasks(records)

    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(render_markdown(report), encoding='utf-8')

    top_themes = ', '.join(item['tag'] for item in report['summary']['top_themes'][:5]) or '暂无'
    print(f'已生成 {json_path} 和 {md_path}')
    print(f'下一轮创意建议先避开高频主题：{top_themes}')
    print('若候选标题命中疑似重复组，请改为评审/补充/测试类下游任务，或更换明确产物路径。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
