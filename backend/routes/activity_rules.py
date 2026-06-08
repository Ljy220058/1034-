from __future__ import annotations

"""活动规则路由。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from ..models import ApiResponse
from ..rules_engine import RuleContext, default_rule_config, evaluate_activity_rules, validate_rule_config

router = APIRouter(prefix='/api/v1/activity-rules', tags=['activity-rules'])


class ActivityRuleContextIn(BaseModel):
    """活动规则计算请求。"""

    now: datetime | None = Field(default=None)
    user_id: int | None = Field(default=None, gt=0)
    role: str = Field(default='member', max_length=20)
    labels: list[str] = Field(default_factory=list)
    usage_count: int = Field(default=0, ge=0)
    priority: str = Field(default='medium', max_length=20)


class ActivityRuleConfigIn(BaseModel):
    """活动规则配置请求。"""

    rules: list[dict[str, object]]


@router.get('', response_model=ApiResponse)
def read_default_rules() -> ApiResponse:
    """读取默认活动规则配置。"""
    return ApiResponse(data=default_rule_config(), message='已返回默认活动规则配置')


@router.post('/validate', response_model=ApiResponse)
def validate_rules(payload: ActivityRuleConfigIn = Body(...)) -> ApiResponse:
    """校验活动规则配置。"""
    try:
        rules = validate_rule_config(payload.model_dump())
    except HTTPException:
        raise
    return ApiResponse(data={'rule_count': len(rules), 'rules': [rule.model_dump() for rule in rules]}, message='规则配置校验通过')


@router.post('/evaluate', response_model=ApiResponse)
def evaluate_rules(payload: ActivityRuleContextIn = Body(...)) -> ApiResponse:
    """计算活动规则结果。"""
    now = payload.now or datetime.now(timezone.utc)
    evaluation = evaluate_activity_rules(
        default_rule_config(),
        RuleContext(
            now=now,
            user_id=payload.user_id,
            role=payload.role,
            labels=set(payload.labels),
            usage_count=payload.usage_count,
            priority=payload.priority,
        ),
    )
    return ApiResponse(data=evaluation.model_dump(), message='已计算活动规则结果')
