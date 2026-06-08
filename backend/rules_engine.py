from __future__ import annotations

"""活动规则引擎。

提供统一的规则配置、校验与可见性/资格计算能力，便于后续扩展新的规则类型。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status

RuleKind = Literal['time_window', 'labels', 'usage_limit', 'priority']
AudienceKind = Literal['all', 'members', 'leaders', 'admins']
ScopeKind = Literal['visible', 'eligible']

_ALLOWED_OPERATION_TYPES = {'visibility', 'eligibility', 'time_window', 'labels', 'usage_limit', 'priority'}
_ALLOWED_TIME_OPERATORS = {'before', 'after', 'between'}
_ALLOWED_LABEL_OPERATORS = {'any', 'all', 'none'}
_ALLOWED_COMPARATORS = {'>=', '>', '<=', '<', '==', '!='}
_ALLOWED_PRIORITY_LEVELS = {'low', 'medium', 'high', 'urgent'}
_ALLOWED_AUDIENCES = {'all', 'members', 'leaders', 'admins'}


@dataclass(frozen=True)
class RuleContext:
    """规则计算上下文。"""

    now: datetime
    user_id: int | None = None
    role: str = 'member'
    labels: set[str] = field(default_factory=set)
    usage_count: int = 0
    priority: str = 'medium'

    def normalized(self) -> 'RuleContext':
        """返回标准化上下文。"""
        current = self.now
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return RuleContext(
            now=current,
            user_id=self.user_id,
            role=self.role,
            labels={str(item).strip() for item in self.labels if str(item).strip()},
            usage_count=max(0, int(self.usage_count)),
            priority=str(self.priority).strip().lower() or 'medium',
        )


@dataclass(frozen=True)
class RuleCondition:
    """规则条件定义。"""

    kind: RuleKind
    operator: str
    value: Any


@dataclass(frozen=True)
class ActivityRule:
    """单条活动规则。"""

    key: str
    scope: ScopeKind
    operation: str
    enabled: bool = True
    conditions: tuple[RuleCondition, ...] = ()
    audience: AudienceKind = 'all'
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        """导出为 JSON 兼容字典。"""
        return {
            'key': self.key,
            'scope': self.scope,
            'operation': self.operation,
            'enabled': self.enabled,
            'conditions': [
                {'kind': condition.kind, 'operator': condition.operator, 'value': condition.value}
                for condition in self.conditions
            ],
            'audience': self.audience,
            'priority': self.priority,
            'metadata': self.metadata,
        }


@dataclass(frozen=True)
class RuleEvaluation:
    """规则计算结果。"""

    visible: bool
    eligible: bool
    matched_rules: list[str]
    blocked_reasons: list[str]
    eligible_reasons: list[str]

    def model_dump(self) -> dict[str, Any]:
        """导出为 JSON 兼容字典。"""
        return {
            'visible': self.visible,
            'eligible': self.eligible,
            'matched_rules': self.matched_rules,
            'blocked_reasons': self.blocked_reasons,
            'eligible_reasons': self.eligible_reasons,
        }


_DEFAULT_RULES: tuple[ActivityRule, ...] = (
    ActivityRule(
        key='time-window-public',
        scope='visible',
        operation='time_window',
        priority=100,
        conditions=(RuleCondition(kind='time_window', operator='before', value='2099-01-01T00:00:00+00:00'),),
        metadata={'description': '默认活动在未来时间窗口内可见'},
    ),
    ActivityRule(
        key='label-members-only',
        scope='eligible',
        operation='labels',
        priority=90,
        conditions=(RuleCondition(kind='labels', operator='none', value=['blacklist']),),
        audience='members',
        metadata={'description': '普通成员在未命中黑名单标签时可报名'},
    ),
)


def _ensure_json_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{name} 必须是对象')
    return value


def _ensure_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{name} 必须是数组')
    return value


def _normalize_priority(value: Any) -> int:
    if not isinstance(value, int):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='priority 必须是整数')
    if value < 0 or value > 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='priority 必须在 0 到 1000 之间')
    return value


def _normalize_rule_kind(value: Any) -> RuleKind:
    if value not in {'time_window', 'labels', 'usage_limit', 'priority'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='不支持的规则类型')
    return value


def _normalize_scope(value: Any) -> ScopeKind:
    if value not in {'visible', 'eligible'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='scope 必须是 visible 或 eligible')
    return value


def _normalize_operation(value: Any) -> str:
    if value not in _ALLOWED_OPERATION_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='不支持的规则操作')
    return value


def _normalize_audience(value: Any) -> AudienceKind:
    if value not in _ALLOWED_AUDIENCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='audience 不合法')
    return value


def _normalize_condition(payload: Any) -> RuleCondition:
    data = _ensure_json_object(payload, 'condition')
    kind = _normalize_rule_kind(data.get('kind'))
    operator = data.get('operator')
    value = data.get('value')
    if kind == 'time_window':
        if operator not in _ALLOWED_TIME_OPERATORS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='time_window 条件 operator 不合法')
        if operator == 'between':
            value = _ensure_list(value, 'time_window.value')
            if len(value) != 2:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='between 必须提供两个时间点')
        elif not isinstance(value, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='time_window.value 必须是字符串')
    elif kind == 'labels':
        if operator not in _ALLOWED_LABEL_OPERATORS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='labels 条件 operator 不合法')
        if not isinstance(value, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='labels.value 必须是非空字符串数组')
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='labels.value 必须是非空字符串数组')
    elif kind == 'usage_limit':
        if operator not in _ALLOWED_COMPARATORS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='usage_limit 条件 operator 不合法')
        if not isinstance(value, int) or value < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='usage_limit.value 必须是非负整数')
    elif kind == 'priority':
        if operator not in {'at_least', 'at_most', 'equals'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='priority 条件 operator 不合法')
        if not isinstance(value, str) or value not in _ALLOWED_PRIORITY_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='priority.value 不合法')
    return RuleCondition(kind=kind, operator=operator, value=value)


def validate_rule_config(config: Any) -> list[ActivityRule]:
    """校验规则配置并转换为规则对象。

    Args:
        config: 外部传入的规则配置。

    Returns:
        已标准化的规则列表。

    Raises:
        HTTPException: 当配置结构或字段不合法时返回 400。
    """
    data = _ensure_json_object(config, 'config')
    raw_rules = data.get('rules')
    rules_payload = _ensure_list(raw_rules, 'rules')
    rules: list[ActivityRule] = []
    seen_keys: set[str] = set()
    for item in rules_payload:
        rule_data = _ensure_json_object(item, 'rule')
        key = str(rule_data.get('key', '')).strip()
        if not key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='rule.key 不能为空')
        if key in seen_keys:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='rule.key 不能重复')
        seen_keys.add(key)
        scope = _normalize_scope(rule_data.get('scope'))
        operation = _normalize_operation(rule_data.get('operation'))
        if scope == 'visible' and operation not in {'visibility', 'time_window'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='visible 规则的 operation 必须是 visibility 或 time_window')
        if scope == 'eligible' and operation not in {'eligibility', 'labels', 'usage_limit', 'priority'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='eligible 规则的 operation 必须是 eligibility、labels、usage_limit 或 priority')
        audience_value = rule_data.get('audience', 'all')
        audience = _normalize_audience(audience_value)
        priority = _normalize_priority(rule_data.get('priority', 0))
        enabled = bool(rule_data.get('enabled', True))
        conditions_payload = _ensure_list(rule_data.get('conditions', []), 'conditions')
        conditions = tuple(_normalize_condition(condition) for condition in conditions_payload)
        metadata = _ensure_json_object(rule_data.get('metadata', {}), 'metadata')
        rules.append(
            ActivityRule(
                key=key,
                scope=scope,
                operation=operation,
                enabled=enabled,
                conditions=conditions,
                audience=audience,
                priority=priority,
                metadata=metadata,
            )
        )
    rules.sort(key=lambda rule: (-rule.priority, rule.key))
    return rules


def default_rule_config() -> dict[str, Any]:
    """返回默认规则配置。"""
    return {'rules': [rule.model_dump() for rule in _DEFAULT_RULES]}


def _match_time_window(condition: RuleCondition, ctx: RuleContext) -> tuple[bool, str | None]:
    if condition.operator == 'before':
        limit = datetime.fromisoformat(str(condition.value))
        if limit.tzinfo is None:
            limit = limit.replace(tzinfo=timezone.utc)
        return ctx.now < limit, None if ctx.now < limit else '已超过时间窗口'
    if condition.operator == 'after':
        limit = datetime.fromisoformat(str(condition.value))
        if limit.tzinfo is None:
            limit = limit.replace(tzinfo=timezone.utc)
        return ctx.now > limit, None if ctx.now > limit else '未进入时间窗口'
    if condition.operator == 'between':
        start, end = [datetime.fromisoformat(str(item)) for item in condition.value]
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        matched = start <= ctx.now <= end
        return matched, None if matched else '不在时间窗口内'
    return False, '时间条件不支持'


def _match_labels(condition: RuleCondition, ctx: RuleContext) -> tuple[bool, str | None]:
    labels = {str(item).strip() for item in condition.value if str(item).strip()}
    if condition.operator == 'any':
        matched = bool(labels & ctx.labels)
    elif condition.operator == 'all':
        matched = labels.issubset(ctx.labels)
    else:
        matched = not bool(labels & ctx.labels)
    return matched, None if matched else '标签条件未命中'


def _match_usage_limit(condition: RuleCondition, ctx: RuleContext) -> tuple[bool, str | None]:
    limit = int(condition.value)
    if condition.operator == '>=':
        matched = ctx.usage_count >= limit
    elif condition.operator == '>':
        matched = ctx.usage_count > limit
    elif condition.operator == '<=':
        matched = ctx.usage_count <= limit
    elif condition.operator == '<':
        matched = ctx.usage_count < limit
    elif condition.operator == '==':
        matched = ctx.usage_count == limit
    else:
        matched = ctx.usage_count != limit
    return matched, None if matched else '次数限制未满足'


def _match_priority(condition: RuleCondition, ctx: RuleContext) -> tuple[bool, str | None]:
    order = {name: index for index, name in enumerate(['low', 'medium', 'high', 'urgent'])}
    current = order.get(ctx.priority, 1)
    target = order[str(condition.value)]
    if condition.operator == 'at_least':
        matched = current >= target
    elif condition.operator == 'at_most':
        matched = current <= target
    else:
        matched = current == target
    return matched, None if matched else '优先级条件未命中'


def evaluate_activity_rules(config: Any, context: RuleContext) -> RuleEvaluation:
    """计算活动规则可见性与资格。

    Args:
        config: 已校验或待校验的规则配置。
        context: 当前用户与活动上下文。

    Returns:
        规则计算结果。
    """
    rules = validate_rule_config(config)
    ctx = context.normalized()
    visible = True
    eligible = True
    matched_rules: list[str] = []
    blocked_reasons: list[str] = []
    eligible_reasons: list[str] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.audience == 'admins' and ctx.role != 'admin':
            continue
        if rule.audience == 'leaders' and ctx.role not in {'admin', 'leader'}:
            continue
        if rule.audience == 'members' and ctx.role not in {'admin', 'leader', 'member'}:
            continue
        matched = True
        reason = None
        for condition in rule.conditions:
            if condition.kind == 'time_window':
                matched, reason = _match_time_window(condition, ctx)
            elif condition.kind == 'labels':
                matched, reason = _match_labels(condition, ctx)
            elif condition.kind == 'usage_limit':
                matched, reason = _match_usage_limit(condition, ctx)
            else:
                matched, reason = _match_priority(condition, ctx)
            if not matched:
                break
        if matched:
            matched_rules.append(rule.key)
            if rule.scope == 'visible':
                visible = visible and matched
                if matched:
                    eligible_reasons.append(f'{rule.key} 满足可见性')
            else:
                eligible = eligible and matched
                if matched:
                    eligible_reasons.append(f'{rule.key} 满足资格')
        else:
            if rule.scope == 'visible':
                visible = False
                if reason:
                    blocked_reasons.append(f'{rule.key}: {reason}')
            else:
                eligible = False
                if reason:
                    blocked_reasons.append(f'{rule.key}: {reason}')
    return RuleEvaluation(visible=visible, eligible=eligible, matched_rules=matched_rules, blocked_reasons=blocked_reasons, eligible_reasons=eligible_reasons)
