from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1', tags=['task-board'])

_MODULE_KEYWORDS: dict[str, set[str]] = {
    'backend': {'后端', '接口', 'API', 'FastAPI', 'SQLite', '数据库', '服务端', '路由', 'endpoint', 'sql', '迁移'},
    'frontend': {'前端', '页面', 'UI', '界面', 'Vue', 'React', 'HTML', 'CSS', 'JS', 'JavaScript', '交互', '组件'},
    'test': {'测试', 'pytest', '单测', '集成测试', '回归', '验证', 'fixture', '断言', '覆盖率'},
    'review': {'评审', 'review', '代码审查', '审查', '安全', '质量', '重构', '规范'},
    'ops': {'部署', '运维', '监控', '健康检查', '日志', '告警', 'cron', '定时', '脚本'},
}
_PRIORITY_ORDER = {'backend': 0, 'frontend': 1, 'test': 2, 'review': 3, 'ops': 4}
_DELIVERY_TYPES: tuple[str, ...] = ('接口', '文档', '测试', '修复', '脚本', '报告', '看板卡片', '自动化流程')


@dataclass(frozen=True)
class BoardCardSuggestion:
    """单条任务灵感卡片。"""

    module: str
    priority: str
    delivery_type: str
    title: str
    description: str
    acceptance_criteria: list[str]
    default_fields: dict[str, str]

    def model_dump(self) -> dict[str, Any]:
        """转换为 JSON 兼容字典。"""
        return {
            'module': self.module,
            'priority': self.priority,
            'delivery_type': self.delivery_type,
            'title': self.title,
            'description': self.description,
            'acceptance_criteria': self.acceptance_criteria,
            'default_fields': self.default_fields,
        }


class TaskBoardIntakeRequest(BaseModel):
    """任务灵感看板创建请求。"""

    topic: str = Field(min_length=1, max_length=200)
    module_hint: str | None = Field(default=None, max_length=80)
    priority_hint: str | None = Field(default=None, max_length=40)
    delivery_hint: str | None = Field(default=None, max_length=80)


def _normalize_text(value: str) -> str:
    """标准化文本用于关键词匹配。"""
    return ' '.join(value.strip().split()).lower()


def _pick_module(topic: str, module_hint: str | None) -> tuple[str, list[str]]:
    """根据主题和模块提示选择模块。"""
    haystack = _normalize_text(f'{topic} {module_hint or ""}')
    reasons: list[str] = []
    module_scores: dict[str, int] = {module: 0 for module in _MODULE_KEYWORDS}

    for module, keywords in _MODULE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in haystack:
                module_scores[module] += 1
                reasons.append(f'命中关键词「{keyword}」→ {module}')

    if module_hint:
        normalized_hint = _normalize_text(module_hint)
        if normalized_hint in module_scores:
            module_scores[normalized_hint] += 2
            reasons.append(f'命中模块提示「{module_hint}」')

    if not reasons:
        return 'backend', ['未命中明确关键词，默认按后端模块处理']

    best_module = max(module_scores.items(), key=lambda item: (item[1], -_PRIORITY_ORDER[item[0]]))[0]
    return best_module, reasons


def _pick_priority(priority_hint: str | None) -> str:
    """选择默认优先级。"""
    if priority_hint:
        normalized = _normalize_text(priority_hint)
        if normalized in {'p0', 'high', 'urgent', '最高', '高'}:
            return 'P0'
        if normalized in {'p1', 'medium', '中', '一般'}:
            return 'P1'
        if normalized in {'p2', 'low', '低'}:
            return 'P2'
    return 'P1'


def _pick_delivery_type(delivery_hint: str | None) -> str:
    """选择交付物类型。"""
    if delivery_hint:
        normalized = _normalize_text(delivery_hint)
        for candidate in _DELIVERY_TYPES:
            if candidate.lower() in normalized:
                return candidate
    return '看板卡片'


def _build_title(module: str, delivery_type: str) -> str:
    """生成中文标题。"""
    mapping = {
        'backend': '后端',
        'frontend': '前端',
        'test': '测试',
        'review': '评审',
        'ops': '运维',
    }
    subject = mapping.get(module, '后端')
    return f'中文创意：{subject}{delivery_type}看板'


def _build_description(topic: str, module: str, delivery_type: str) -> str:
    """生成任务描述。"""
    return f'围绕「{topic}」设计一个可快速录入的{delivery_type}，优先落地到{module}模块，并保证后续可继续扩展为自动化看板生成流程。'


def _build_acceptance_criteria(module: str, delivery_type: str) -> list[str]:
    """生成默认验收标准。"""
    return [
        f'产出一个可运行的{delivery_type}或模块。',
        'pytest 全绿，新增测试覆盖核心分支。',
        '错误返回统一为 {"detail": "中文描述"}，成功返回统一为 {"data": ..., "message": "中文"}。',
        f'默认字段规则可直接扩展到{module}相关任务。',
    ]


def _build_default_fields(module: str, priority: str, delivery_type: str) -> dict[str, str]:
    """生成默认字段规则。"""
    return {
        'module': module,
        'priority': priority,
        'delivery_type': delivery_type,
        'status': 'todo',
        'assignee': 'backend-dev',
        'workspace_kind': 'dir',
        'response_format': '{"data": ..., "message": "中文"}',
        'error_format': '{"detail": "中文描述"}',
    }


def _suggest_cards(topic: str, module_hint: str | None, priority_hint: str | None, delivery_hint: str | None) -> list[BoardCardSuggestion]:
    """生成三条可直接落地的默认卡片规则。"""
    module, reasons = _pick_module(topic, module_hint)
    priority = _pick_priority(priority_hint)
    delivery_type = _pick_delivery_type(delivery_hint)
    cards: list[BoardCardSuggestion] = []
    variants = (
        ('基础接口', '适合先做最小可运行端点，保证验收闭环。'),
        ('测试补强', '适合先补 pytest，再推进实现。'),
        ('错误分支', '适合优先统一结构化错误返回。'),
    )
    for suffix, extra in variants:
        title = _build_title(module, delivery_type)
        cards.append(
            BoardCardSuggestion(
                module=module,
                priority=priority,
                delivery_type=delivery_type,
                title=title,
                description=f"{_build_description(topic, module, delivery_type)} {extra} {'；'.join(reasons[:2])}",
                acceptance_criteria=_build_acceptance_criteria(module, delivery_type),
                default_fields=_build_default_fields(module, priority, delivery_type),
            )
        )
    return cards


class TaskBoardIntakeResponse(BaseModel):
    """任务灵感看板响应。"""

    count: int
    cards: list[dict[str, Any]]


@router.post('/task-board/intake', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_task_board_intake(payload: TaskBoardIntakeRequest) -> ApiResponse:
    """生成三条可直接落地的任务灵感卡片。"""
    cards = _suggest_cards(payload.topic, payload.module_hint, payload.priority_hint, payload.delivery_hint)
    return ApiResponse(
        data={
            'count': len(cards),
            'cards': [card.model_dump() for card in cards],
        },
        message='已生成任务灵感看板',
    )


@router.get('/task-board/intake', response_model=ApiResponse)
def read_task_board_intake() -> ApiResponse:
    """返回任务灵感看板的默认规则说明。"""
    cards = _suggest_cards('任务灵感看板', 'backend', 'P1', '看板卡片')
    return ApiResponse(
        data={
            'count': len(cards),
            'cards': [card.model_dump() for card in cards],
            'default_rules': [
                '按模块分类：backend / frontend / test / review / ops。',
                '按优先级分类：P0 / P1 / P2。',
                '按交付物分类：接口 / 文档 / 测试 / 修复 / 脚本 / 报告 / 看板卡片 / 自动化流程。',
            ],
        },
        message='已返回任务灵感看板默认规则',
    )
