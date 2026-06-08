from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    '跑步数据': ('跑步', '跑量', '配速', '公里', '里程', '签到', '报名', '活动参与', '跑团', '训练'),
    '校园风格': ('校园', '校区', '社团', '深技大', '学生', '排行榜', '挑战赛'),
    '瀑布流': ('瀑布流', '卡片流', '活动列表', '活动卡片', '信息流'),
    '导入向导': ('导入', '向导', '预检', '错误文案', '批量导入', 'CSV', 'Excel'),
    '看板调度': ('看板', '任务', 'worker', '分流', '空闲', '调度', '阻塞', '验收', '重复', '去重'),
    '文档方案': ('文档', '说明', '指南', '方案', '清单', '规格', '报告'),
    '安全权限': ('安全', '权限', '审计', 'token', '密码', '认证'),
}

STOP_WORDS = {
    '中文', '创意', '任务', '功能', '添加', '实现', '设计', '整理', '补充', '生成', '一个', '当前', '项目',
    '页面', '接口', '说明', '方案', '清单', '报告', '进行', '提供', '避免', '后续', '创建', '已有', '输出',
}

SYNONYMS: dict[str, str] = {
    '公里': '跑量',
    '里程': '跑量',
    '配速': '跑步数据',
    '签到': '跑步数据',
    '报名': '活动参与',
    '深技大': '校园',
    '社团': '校园',
    '卡片流': '瀑布流',
    '信息流': '瀑布流',
    '批量导入': '导入',
    '预检': '导入',
    '错误文案': '导入',
    '分流': '看板调度',
    '空闲': '看板调度',
    '重复': '去重',
    '审核': '评审',
    '审查': '评审',
}

TOKEN_RE = re.compile(r'[\u4e00-\u9fffA-Za-z0-9_+-]+')
PATH_RE = re.compile(r'(?:docs|backend|frontend|tests|scripts)/[^\s，。；：、)）`]+')


@dataclass(frozen=True)
class KanbanTaskRecord:
    """看板任务的轻量输入记录。"""

    task_id: str
    title: str
    body: str = ''
    assignee: str | None = None
    status: str | None = None
    workspace_path: str | None = None
    created_at: int | None = None


def normalize_text(value: str) -> str:
    """归一化中文创意文本，便于关键词和指纹比较。"""
    text = unicodedata.normalize('NFKC', value or '').lower()
    text = re.sub(r'[：:，,。；;、\-—_`"“”\'\[\]（）(){}<>/\\|]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokenize(value: str) -> list[str]:
    """抽取粗粒度中文/英文 token，并应用少量同义词归一。"""
    normalized = normalize_text(value)
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(normalized):
        # 连续中文句子会被正则作为一个长 token 命中；这类 token 不稳定，
        # 依赖下方主题词表补充更可解释的短词。
        if any('\u4e00' <= char <= '\u9fff' for char in raw) and len(raw) > 6:
            continue
        token = SYNONYMS.get(raw) or raw
        if len(token) <= 1 or token in STOP_WORDS:
            continue
        tokens.append(str(token))
    # 中文短语关键词常被整段吞掉；额外按词表补充命中词，提升主题可解释性。
    for words in THEME_KEYWORDS.values():
        for word in words:
            if word.lower() in normalized:
                tokens.append(SYNONYMS.get(word, word))
    return tokens


def extract_theme_tags(text: str) -> list[dict[str, Any]]:
    """根据关键词抽取主题标签和命中证据。"""
    normalized = normalize_text(text)
    tags: list[dict[str, Any]] = []
    for tag, keywords in THEME_KEYWORDS.items():
        hits = sorted({word for word in keywords if word.lower() in normalized})
        if hits:
            tags.append({'tag': tag, 'score': len(hits), 'evidence': hits})
    return sorted(tags, key=lambda item: (-item['score'], item['tag']))


def duplicate_fingerprint(title: str, body: str = '') -> str:
    """生成面向创意任务的可解释去重指纹。"""
    text = f'{title} {body}'
    tokens = tokenize(text)
    important = [token for token, _ in Counter(tokens).most_common(12)]
    if not important:
        important = normalize_text(title).split()[:8]
    return '|'.join(sorted(dict.fromkeys(important)))


def duplicate_risk(left: KanbanTaskRecord, right: KanbanTaskRecord) -> dict[str, Any]:
    """比较两个任务是否相近，返回诊断字段。"""
    left_text = f'{left.title} {left.body}'
    right_text = f'{right.title} {right.body}'
    left_tokens = set(tokenize(left_text))
    right_tokens = set(tokenize(right_text))
    overlap = sorted(left_tokens & right_tokens)
    union_size = max(1, len(left_tokens | right_tokens))
    overlap_ratio = len(overlap) / union_size
    left_paths = set(PATH_RE.findall(left_text))
    right_paths = set(PATH_RE.findall(right_text))
    same_paths = sorted(left_paths & right_paths)
    same_workspace = bool(left.workspace_path and left.workspace_path == right.workspace_path)
    same_assignee = bool(left.assignee and left.assignee == right.assignee)
    score = 0
    reasons: list[str] = []
    if overlap_ratio >= 0.45 and len(overlap) >= 3:
        score += 3
        reasons.append('标题/正文核心词高度重叠')
    elif overlap_ratio >= 0.25 and len(overlap) >= 2:
        score += 1
        reasons.append('标题/正文核心词部分重叠')
    if same_paths:
        score += 4
        reasons.append('目标产物路径相同')
    if same_workspace:
        score += 1
        reasons.append('工作区相同')
    if same_assignee:
        score += 1
        reasons.append('负责人相同')
    if left.status in {'todo', 'ready', 'running', 'blocked'} or right.status in {'todo', 'ready', 'running', 'blocked'}:
        score += 1
        reasons.append('存在未完成任务')
    if score >= 5:
        level = '高'
        suggestion = '跳过创建，改为引用已有任务或写明评审/补充关系'
    elif score >= 3:
        level = '中'
        suggestion = '创建前补充新增价值、上游任务和不同产物路径'
    else:
        level = '低'
        suggestion = '可创建，保留主题标签用于后续趋势观察'
    return {
        'risk_level': level,
        'score': score,
        'reasons': reasons,
        'overlap_keywords': overlap[:12],
        'same_paths': same_paths,
        'suggestion': suggestion,
    }


def summarize_tasks(records: Iterable[KanbanTaskRecord]) -> dict[str, Any]:
    """汇总看板任务主题、趋势标签和去重诊断输入。"""
    tasks = list(records)
    theme_counter: Counter[str] = Counter()
    keyword_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    tag_examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    fingerprints: dict[str, list[dict[str, str]]] = defaultdict(list)

    for task in tasks:
        text = f'{task.title} {task.body}'
        status_counter[task.status or 'unknown'] += 1
        for token in tokenize(text):
            keyword_counter[token] += 1
        tags = extract_theme_tags(text)
        for tag in tags:
            theme_counter[tag['tag']] += tag['score']
            if len(tag_examples[tag['tag']]) < 5:
                tag_examples[tag['tag']].append({'task_id': task.task_id, 'title': task.title})
        fingerprint = duplicate_fingerprint(task.title, task.body)
        if fingerprint:
            fingerprints[fingerprint].append({'task_id': task.task_id, 'title': task.title, 'status': task.status or 'unknown'})

    duplicate_groups = [
        {'fingerprint': fp, 'items': items, 'count': len(items)}
        for fp, items in fingerprints.items()
        if len(items) > 1
    ]
    duplicate_groups.sort(key=lambda item: (-item['count'], item['fingerprint']))

    return {
        'summary': {
            'total_tasks': len(tasks),
            'status_counts': dict(status_counter),
            'top_themes': [{'tag': tag, 'score': score, 'examples': tag_examples[tag]} for tag, score in theme_counter.most_common()],
            'top_keywords': [{'keyword': key, 'count': count} for key, count in keyword_counter.most_common(20)],
        },
        'dedupe_rules': [
            '同一工作区且目标产物路径相同：高风险，跳过创建',
            '未完成任务与候选任务核心词重叠达到 45% 且不少于 3 个：高风险，跳过或改为下游任务',
            '同一负责人在同主题上已有 ready/running/blocked：中高风险，避免并行创建',
            '候选任务命中跑步数据、校园风格、瀑布流、导入向导等趋势标签时，必须检查相同标签下最近任务示例',
            '允许评审/补充/测试类下游任务，但标题和正文必须写明上游产物与新增价值',
        ],
        'next_round_guidance': [
            '创建新创意前先读取 summary.top_themes 前 5 项，优先避开高频主题或改为明确下游评审/测试任务',
            '候选标题若命中 duplicate_groups 中的指纹词，必须更换作用对象、交付物路径或直接跳过',
            '正文必须写明具体产物路径、与相近任务的差异点，以及单个 worker 30 分钟内可完成的验收步骤',
        ],
        'local_run_example': {
            'command': 'python scripts/generate_creative_idea_tags.py --db "$HERMES_KANBAN_DB" --limit 200',
            'json_output': 'docs/中文创意库标签摘要.json',
            'markdown_output': 'docs/中文创意库标签摘要.md',
            'usage': '下一轮创意侦察先查看 top_themes 和 duplicate_groups；若候选任务命中高频主题或疑似重复组，就换模块、换产物路径，或改成评审/补充/测试类下游任务。',
        },
        'duplicate_groups': duplicate_groups[:20],
    }


def load_tasks_from_sqlite(db_path: str | Path, *, limit: int = 200) -> list[KanbanTaskRecord]:
    """从 Hermes Kanban SQLite 读取近期任务。"""
    path = Path(db_path).expanduser()
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            '''
            SELECT id, title, COALESCE(body, '') AS body, assignee, status, workspace_path, created_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
    return [
        KanbanTaskRecord(
            task_id=row['id'],
            title=row['title'],
            body=row['body'],
            assignee=row['assignee'],
            status=row['status'],
            workspace_path=row['workspace_path'],
            created_at=row['created_at'],
        )
        for row in rows
    ]


def render_markdown(report: dict[str, Any]) -> str:
    """把标签摘要渲染为 Markdown，便于 docs 或人工审阅。"""
    lines = ['# 中文创意库标签摘要', '']
    summary = report['summary']
    lines.append(f"- 任务总数：{summary['total_tasks']}")
    lines.append(f"- 状态分布：{json.dumps(summary['status_counts'], ensure_ascii=False)}")
    lines.append('')
    lines.append('## 趋势标签')
    for item in summary['top_themes']:
        examples = '；'.join(f"{ex['task_id']} {ex['title']}" for ex in item['examples'])
        lines.append(f"- {item['tag']}（score={item['score']}）：{examples}")
    lines.append('')
    lines.append('## 高频关键词')
    lines.append('、'.join(f"{item['keyword']}({item['count']})" for item in summary['top_keywords']))
    lines.append('')
    lines.append('## 去重规则')
    for rule in report['dedupe_rules']:
        lines.append(f'- {rule}')
    lines.append('')
    lines.append('## 下一轮创意使用方式')
    for item in report.get('next_round_guidance', []):
        lines.append(f'- {item}')
    example = report.get('local_run_example') or {}
    if example:
        lines.append('')
        lines.append('## 本地运行示例')
        lines.append(f"- 命令：`{example['command']}`")
        lines.append(f"- JSON 输出：`{example['json_output']}`")
        lines.append(f"- Markdown 输出：`{example['markdown_output']}`")
        lines.append(f"- 用法：{example['usage']}")
    lines.append('')
    lines.append('## 疑似重复组')
    if not report['duplicate_groups']:
        lines.append('- 暂无疑似重复组')
    for group in report['duplicate_groups']:
        titles = '；'.join(f"{item['task_id']} {item['title']}[{item['status']}]" for item in group['items'])
        lines.append(f"- {group['fingerprint']}：{titles}")
    return '\n'.join(lines) + '\n'
