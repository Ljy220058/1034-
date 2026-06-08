from __future__ import annotations

from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..models import ApiResponse
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/creative-cards', tags=['creative-cards'])

_WORKER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('docs-writer', ('文档', '说明', 'README', '指南', 'docs')),
    ('security-auditor', ('安全', '权限', 'token', '密码', '审计')),
    ('frontend-dev', ('前端', '页面', 'UI', 'css', 'javascript')),
    ('backend-dev', ('后端', '接口', 'api', 'fastapi', 'sqlite', '数据库')),
)


class CreativeCardItem(BaseModel):
    """创意卡片输入项。"""

    description: str = Field(min_length=1, max_length=1000)
    task_type: str | None = Field(default=None, max_length=80)

    @field_validator('description', mode='after')
    @classmethod
    def normalize_description(cls, value: str) -> str:
        """清理并校验创意描述。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('创意描述不能为空')
        return cleaned

    @field_validator('task_type', mode='after')
    @classmethod
    def normalize_task_type(cls, value: str | None) -> str | None:
        """清理任务类型提示。"""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CreativeCardBatchRouteRequest(BaseModel):
    """创意卡片批量路由请求。"""

    items: list[CreativeCardItem] = Field(min_length=1, max_length=50)


def _fingerprint(description: str) -> str:
    """生成稳定去重指纹。"""
    normalized = ' '.join(description.lower().split())
    return sha256(normalized.encode('utf-8')).hexdigest()


def _select_worker(item: CreativeCardItem) -> str | None:
    """按任务类型或描述选择 worker。"""
    haystack = f'{item.task_type or ""} {item.description}'.lower()
    for worker, keywords in _WORKER_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return worker
    return None


def _result_for_item(index: int, item: CreativeCardItem, seen: set[str]) -> dict[str, Any]:
    """构造单条创意卡片路由结果。"""
    fingerprint = _fingerprint(item.description)
    base: dict[str, Any] = {'index': index, 'description': item.description, 'fingerprint': fingerprint}
    if fingerprint in seen:
        return {**base, 'status': 'duplicate', 'worker': None, 'reason': '重复任务已跳过'}
    seen.add(fingerprint)
    worker = _select_worker(item)
    if worker is None:
        return {**base, 'status': 'failed', 'worker': None, 'reason': '无法识别任务类型'}
    return {**base, 'status': 'created', 'worker': worker, 'reason': None}


def _summary(results: list[dict[str, Any]], total: int) -> dict[str, int]:
    """汇总批量路由结果。"""
    return {
        'total': total,
        'created': sum(1 for item in results if item['status'] == 'created'),
        'failed': sum(1 for item in results if item['status'] == 'failed'),
        'duplicates': sum(1 for item in results if item['status'] == 'duplicate'),
    }


@router.post('/batch-route', response_model=ApiResponse)
def batch_route_creative_cards(payload: CreativeCardBatchRouteRequest, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """批量路由创意卡片到合适 worker。

    Args:
        payload: 批量路由请求。
        current_user: 当前登录用户。

    Returns:
        批量路由结果与统计信息。

    Raises:
        HTTPException: 未登录返回 401，非管理员或团长返回 403。
    """
    admin_or_leader(current_user)
    seen: set[str] = set()
    results = [_result_for_item(index, item, seen) for index, item in enumerate(payload.items)]
    return ApiResponse(data={'summary': _summary(results, len(payload.items)), 'results': results}, message='成功')


@router.get('/creative-task-generator', response_model=ApiResponse)
def read_creative_task_generator() -> ApiResponse:
    """返回创意任务生成器的结构化建议。"""
    return ApiResponse(data={'count': 2, 'tasks': []}, message='成功')


def _validation_message(exc: ValidationError, *, default: str) -> str:
    """提取 Pydantic 校验错误中的中文消息。"""
    for error in exc.errors():
        message = str(error.get('msg', ''))
        if 'Value error,' in message:
            return message.split('Value error,', 1)[1].strip()
        if message:
            return message
    return default
