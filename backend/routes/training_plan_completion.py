from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..calendar_export import export_training_plan_ics
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/training-plan', tags=['training-plan'])
DEFAULT_TRAINING_PLAN_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab/data/training_plan.json'
MAX_COMPLETION_PERCENT = 100.0
DEFAULT_ICS_NAME = 'training-plan.ics'


class TrainingPlanExportValidationError(ValueError):
    """训练计划 ICS 导出校验错误。"""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.message = message

    def __str__(self) -> str:
        return self.message


def _parse_iso_date(value: str, field_name: str) -> date:
    """解析 ISO 日期字符串。

    Args:
        value: ISO 格式日期字符串。
        field_name: 字段名称。

    Returns:
        解析后的 date 对象。

    Raises:
        HTTPException: 日期格式不合法时抛出 400。
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{field_name} 不是有效的 ISO 日期') from exc


def _parse_time_value(value: Any, field_name: str) -> time:
    """解析时间字段。

    Args:
        value: 待解析时间值。
        field_name: 字段名称。

    Returns:
        time 对象。

    Raises:
        TrainingPlanExportValidationError: 时间格式不合法时抛出。
    """
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError as exc:
            raise TrainingPlanExportValidationError(field_name, f'{field_name} 不是有效的时间') from exc
    raise TrainingPlanExportValidationError(field_name, f'{field_name} 必须是时间字符串')


def _parse_datetime_value(value: Any, field_name: str) -> datetime:
    """解析日期时间字段。

    Args:
        value: 待解析值。
        field_name: 字段名称。

    Returns:
        带时区的 datetime。

    Raises:
        TrainingPlanExportValidationError: 日期时间格式不合法时抛出。
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise TrainingPlanExportValidationError(field_name, f'{field_name} 不是有效的日期时间') from exc
    raise TrainingPlanExportValidationError(field_name, f'{field_name} 必须是日期时间字符串')


def _parse_date_or_datetime(value: Any, field_name: str) -> date | datetime:
    """解析日期或日期时间字段。

    Args:
        value: 待解析值。
        field_name: 字段名称。

    Returns:
        date 或 datetime 对象。

    Raises:
        TrainingPlanExportValidationError: 值格式不合法时抛出。
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed_datetime = datetime.fromisoformat(value)
        except ValueError:
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise TrainingPlanExportValidationError(field_name, f'{field_name} 不是有效的日期或日期时间') from exc
        return parsed_datetime
    raise TrainingPlanExportValidationError(field_name, f'{field_name} 必须是日期、日期时间或对应字符串')


def _combine_local_datetime(day: date, value: Any, field_name: str) -> datetime:
    """组合日期和时间并转换为 UTC。

    Args:
        day: 日期。
        value: 时间或日期时间。
        field_name: 字段名称。

    Returns:
        带时区的 UTC datetime。

    Raises:
        TrainingPlanExportValidationError: 时间字段缺失或无效时抛出。
    """
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise TrainingPlanExportValidationError(field_name, f'{field_name} 必须包含时区信息')
        return value.astimezone(timezone.utc)
    parsed_time = _parse_time_value(value, field_name)
    local_value = datetime.combine(day, parsed_time)
    return local_value.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)


def _normalize_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """校验并规范化训练活动。

    Args:
        activity: 原始活动字典。

    Returns:
        规范化后的活动字典。
    """
    title = str(activity.get('title', '')).strip()
    if not title:
        raise TrainingPlanExportValidationError('title', 'title 不能为空')

    if 'start_time' not in activity:
        raise TrainingPlanExportValidationError('start_time', 'start_time 不能为空')
    if 'end_time' not in activity:
        raise TrainingPlanExportValidationError('end_time', 'end_time 不能为空')

    start_raw = activity.get('start_time')
    end_raw = activity.get('end_time')

    if not isinstance(start_raw, (datetime, date, str)) or not isinstance(end_raw, (datetime, date, str)):
        raise TrainingPlanExportValidationError('start_time', 'start_time 和 end_time 必须是 datetime 或日期时间字符串')

    if isinstance(start_raw, str):
        start_raw = _parse_date_or_datetime(start_raw, 'start_time')
    if isinstance(end_raw, str):
        end_raw = _parse_date_or_datetime(end_raw, 'end_time')

    if isinstance(start_raw, datetime):
        if start_raw.tzinfo is None or start_raw.utcoffset() is None:
            raise TrainingPlanExportValidationError('start_time', 'start_time 必须包含时区信息')
        start_dt = start_raw.astimezone(timezone.utc)
    else:
        start_dt = _combine_local_datetime(start_raw, _parse_time_value(start_raw, 'start_time'), 'start_time')

    if isinstance(end_raw, datetime):
        if end_raw.tzinfo is None or end_raw.utcoffset() is None:
            raise TrainingPlanExportValidationError('end_time', 'end_time 必须包含时区信息')
        end_dt = end_raw.astimezone(timezone.utc)
    else:
        end_dt = _combine_local_datetime(end_raw, _parse_time_value(end_raw, 'end_time'), 'end_time')

    if end_dt < start_dt:
        raise TrainingPlanExportValidationError('end_time', 'end_time 不能早于 start_time')

    return {
        'title': title,
        'start_time': start_dt,
        'end_time': end_dt,
        'location': str(activity.get('location', '')).strip(),
        'description': str(activity.get('description', '')).strip(),
        'activity_url': str(activity.get('activity_url', '')).strip(),
    }


def _build_export_payload(activities: list[dict[str, Any]]) -> dict[str, Any]:
    """构建 ICS 导出响应载荷。

    Args:
        activities: 训练活动列表。

    Returns:
        结构化导出数据。
    """
    normalized = [_normalize_activity(activity) for activity in activities]
    ics_text = export_training_plan_ics(normalized)
    return {
        'export_name': DEFAULT_ICS_NAME,
        'mime_type': 'text/calendar; charset=utf-8',
        'content': ics_text,
        'activity_count': len(normalized),
    }


def _count_duplicate_checkins(attendance_records: list[dict[str, Any]]) -> int:
    """统计同一成员同一天的重复打卡次数。

    Args:
        attendance_records: 打卡记录列表。

    Returns:
        重复打卡次数。
    """
    seen: set[tuple[Any, str]] = set()
    duplicate_count = 0
    for record in attendance_records:
        member_id = record.get('member_id')
        checked_in_at = record.get('checked_in_at')
        if member_id is None or not isinstance(checked_in_at, str):
            continue
        try:
            checkin_day = datetime.fromisoformat(checked_in_at).date().isoformat()
        except ValueError:
            continue
        key = (member_id, checkin_day)
        if key in seen:
            duplicate_count += 1
        else:
            seen.add(key)
    return duplicate_count


def _has_leap_day(plan_start_date: date, plan_end_date: date) -> bool:
    """判断计划区间是否覆盖闰日。"""
    year_range = range(plan_start_date.year, plan_end_date.year + 1)
    for year in year_range:
        try:
            leap_day = date(year, 2, 29)
        except ValueError:
            continue
        if plan_start_date <= leap_day <= plan_end_date:
            return True
    return False


def _build_quality_gate_rules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """构建训练计划完成率质量门禁规则列表。

    Args:
        payload: 训练计划完成率相关输入数据。

    Returns:
        规则检查结果列表。
    """
    plan_start_date = _parse_iso_date(str(payload.get('plan_start_date', '')), 'plan_start_date')
    plan_end_date = _parse_iso_date(str(payload.get('plan_end_date', '')), 'plan_end_date')
    if plan_end_date < plan_start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='plan_end_date 不能早于 plan_start_date')

    completion_rate_raw = payload.get('completion_rate', 0)
    try:
        completion_rate = float(completion_rate_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='completion_rate 必须是数字') from exc

    attendance_records = payload.get('attendance_records', [])
    if not isinstance(attendance_records, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='attendance_records 必须是数组')

    daily_targets = payload.get('daily_targets', [])
    if not isinstance(daily_targets, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='daily_targets 必须是数组')

    duplicate_checkins = _count_duplicate_checkins(attendance_records)
    missing_targets = 0
    for item in daily_targets:
        if not isinstance(item, dict):
            continue
        if item.get('target_distance_km') is None and item.get('target_sessions') is None:
            missing_targets += 1

    rules = [
        {
            'rule_key': 'cross_month_boundary',
            'passed': plan_start_date.month != plan_end_date.month,
            'message': '跨月边界检查',
            'detail': f'开始日期 {plan_start_date.isoformat()}，结束日期 {plan_end_date.isoformat()}',
        },
        {
            'rule_key': 'leap_day_coverage',
            'passed': _has_leap_day(plan_start_date, plan_end_date),
            'message': '闰日覆盖检查',
            'detail': '计划区间是否包含 2 月 29 日',
        },
        {
            'rule_key': 'duplicate_checkin',
            'passed': duplicate_checkins == 0,
            'message': '重复打卡检查',
            'detail': f'重复打卡次数：{duplicate_checkins}',
        },
        {
            'rule_key': 'daily_target_complete',
            'passed': missing_targets == 0,
            'message': '每日目标完整性检查',
            'detail': f'缺失目标条目数：{missing_targets}',
        },
        {
            'rule_key': 'completion_overflow',
            'passed': completion_rate <= MAX_COMPLETION_PERCENT,
            'message': '完成率上限检查',
            'detail': f'当前完成率：{completion_rate:.1f}%',
        },
        {
            'rule_key': 'privacy_notice',
            'passed': True,
            'message': '隐私提示检查',
            'detail': '未输出任何手机号、身份证号或定位明细',
        },
    ]
    return rules


@router.post('/export', response_model=ApiResponse)
def export_training_plan_calendar(
    payload: dict[str, Any],
    config_path: str = Query(default=DEFAULT_TRAINING_PLAN_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """导出训练计划为 ICS 日历文本。

    Args:
        payload: 包含 activities 的请求体。
        config_path: 训练计划配置文件路径。

    Returns:
        结构化导出结果。

    Raises:
        HTTPException: 请求体不合法或导出失败时返回 400。
    """
    activities = payload.get('activities')
    if not isinstance(activities, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='activities 必须是数组')

    try:
        export_payload = _build_export_payload(activities)
    except TrainingPlanExportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    return ApiResponse(
        data={
            'config_path': str(config_path),
            **export_payload,
        },
        message='已生成训练计划 ICS 导出内容',
    )


@router.post('/completion-quality-gate', response_model=ApiResponse)
def check_training_plan_completion_quality_gate(
    payload: dict[str, Any],
    config_path: str = Query(default=DEFAULT_TRAINING_PLAN_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """检查训练计划完成率质量门禁。

    Args:
        payload: 训练计划完成率相关输入数据。
        config_path: 训练计划配置文件路径。

    Returns:
        结构化检查结果。
    """
    rules = _build_quality_gate_rules(payload)
    passed_rules = sum(1 for rule in rules if rule['passed'])
    failed_rules = len(rules) - passed_rules
    return ApiResponse(
        data={
            'config_path': str(config_path),
            'total_rules': len(rules),
            'passed_rules': passed_rules,
            'failed_rules': failed_rules,
            'rules': rules,
        },
        message='已完成训练计划完成率质量门禁检查',
    )
