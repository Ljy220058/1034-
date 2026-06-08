from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

PROMPT_STATUSES = {'todo', 'ready'}


@dataclass(frozen=True)
class IdleCardPrompt:
    """空闲 worker 未领取卡片提醒。"""

    task_id: str
    task_key: str
    title: str
    assignee: str
    idle_minutes: int
    suggested_priority: str
    reminder: str

    def as_dict(self) -> dict[str, str | int]:
        """转换为 JSON 可序列化字典。"""
        return {
            'task_id': self.task_id,
            'task_key': self.task_key,
            'title': self.title,
            'assignee': self.assignee,
            'idle_minutes': self.idle_minutes,
            'suggested_priority': self.suggested_priority,
            'reminder': self.reminder,
        }


def profile_name(worker: dict[str, Any]) -> str:
    """提取稳定 worker 标识。

    Args:
        worker: Worker 行数据。

    Returns:
        worker_key 或 name。
    """
    return str(worker.get('worker_key') or worker.get('name') or '').strip()


def parse_updated_at(value: str | None) -> datetime | None:
    """解析任务更新时间。

    Args:
        value: SQLite 或 ISO 格式时间文本。

    Returns:
        带时区的 datetime，无法解析时返回 None。
    """
    if not value:
        return None
    cleaned = value.replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def priority_label(idle_minutes: int) -> str:
    """根据等待分钟数给出建议优先级。"""
    if idle_minutes >= 240:
        return 'urgent'
    if idle_minutes >= 120:
        return 'high'
    return 'normal'


def build_idle_card_prompts(
    idle_workers: list[dict[str, Any]],
    pending_tasks: list[dict[str, Any]],
    threshold_minutes: int,
    now: datetime | None = None,
) -> list[IdleCardPrompt]:
    """生成分配给空闲 worker 的未领取卡片提醒。

    Args:
        idle_workers: 当前空闲 worker 列表。
        pending_tasks: 待处理任务列表。
        threshold_minutes: 触发提醒的最小等待分钟数。
        now: 当前时间，测试可注入。

    Returns:
        按建议优先级和等待时间排序的中文提醒列表。
    """
    current_time = now or datetime.now(timezone.utc)
    idle_worker_keys = {profile_name(worker) for worker in idle_workers}
    prompts: list[IdleCardPrompt] = []
    for task in pending_tasks:
        assignee = str(task.get('assignee') or '').strip()
        status = str(task.get('status') or '')
        if not assignee or assignee not in idle_worker_keys or status not in PROMPT_STATUSES:
            continue
        updated_at = parse_updated_at(str(task.get('updated_at') or ''))
        if updated_at is None:
            continue
        idle_minutes = max(0, int((current_time - updated_at).total_seconds() // 60))
        if idle_minutes < threshold_minutes:
            continue
        title = str(task.get('title') or '未命名任务')
        priority = priority_label(idle_minutes)
        prompts.append(
            IdleCardPrompt(
                task_id=str(task.get('task_id') or task.get('task_key') or ''),
                task_key=str(task.get('task_key') or ''),
                title=title,
                assignee=assignee,
                idle_minutes=idle_minutes,
                suggested_priority=priority,
                reminder=f'{assignee} 当前空闲，卡片“{title}”已等待约 {idle_minutes} 分钟未被领取，建议按 {priority} 优先级提醒处理。',
            )
        )
    priority_rank = {'urgent': 0, 'high': 1, 'normal': 2}
    return sorted(prompts, key=lambda item: (priority_rank[item.suggested_priority], -item.idle_minutes, item.task_key))
