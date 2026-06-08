from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CRLF = '\r\n'
VCALENDAR_HEADER = 'BEGIN:VCALENDAR'
VCALENDAR_VERSION = 'VERSION:2.0'
VCALENDAR_PRODID = '-//1034 Running Club//Training Plan Export//CN'
VCALENDAR_CALSCALE = 'CALSCALE:GREGORIAN'
VCALENDAR_METHOD = 'METHOD:PUBLISH'
VEVENT_BEGIN = 'BEGIN:VEVENT'
VEVENT_END = 'END:VEVENT'
VCALENDAR_END = 'END:VCALENDAR'


class CalendarActivityValidationError(ValueError):
    """训练计划 ICS 导出校验错误。"""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.message = message

    def __str__(self) -> str:
        return self.message


def _ensure_datetime(value: Any, field_name: str) -> datetime:
    """校验并返回 datetime 值。

    Args:
        value: 待校验值。
        field_name: 字段名称。

    Returns:
        转换为 UTC 的 datetime。

    Raises:
        CalendarActivityValidationError: 值不是带时区的 datetime 时抛出。
    """
    if not isinstance(value, datetime):
        raise CalendarActivityValidationError(field_name=field_name, message=f'{field_name} 必须是 datetime')
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarActivityValidationError(field_name=field_name, message=f'{field_name} 必须包含时区信息')
    return value.astimezone(timezone.utc)


def _normalize_text(value: Any) -> str:
    """将可选文本标准化为字符串。"""
    if value is None:
        return ''
    return str(value)


def _escape_ics_text(value: str) -> str:
    """按 ICS 规则转义文本。"""
    return value.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n')


def _format_utc(dt: datetime) -> str:
    """格式化 UTC 时间为 ICS 文本。"""
    return dt.strftime('%Y%m%dT%H%M%SZ')


def _validate_activity(activity: dict[str, Any]) -> dict[str, str]:
    """校验单条训练活动并返回规范化字段。"""
    title = _normalize_text(activity.get('title')).strip()
    if not title:
        raise CalendarActivityValidationError(field_name='title', message='title 不能为空')

    start_time = _ensure_datetime(activity.get('start_time'), 'start_time')
    end_time = _ensure_datetime(activity.get('end_time'), 'end_time')
    if end_time < start_time:
        raise CalendarActivityValidationError(field_name='end_time', message='end_time 不能早于 start_time')

    description = _escape_ics_text(_normalize_text(activity.get('description')).strip())
    activity_url = _escape_ics_text(_normalize_text(activity.get('activity_url')).strip())
    if activity_url:
        description = f'{description}\n{activity_url}' if description else activity_url

    return {
        'title': title,
        'start_time': _format_utc(start_time),
        'end_time': _format_utc(end_time),
        'location': _escape_ics_text(_normalize_text(activity.get('location')).strip()),
        'description': description,
    }


def _event_lines(activity: dict[str, str], index: int) -> list[str]:
    """生成单条 VEVENT 的行内容。"""
    lines = [
        VEVENT_BEGIN,
        f'UID:training-plan-{index}@1034-running-club',
        f'DTSTAMP:{_format_utc(datetime.now(timezone.utc))}',
        f'SUMMARY:{activity["title"]}',
        f'DTSTART:{activity["start_time"]}',
        f'DTEND:{activity["end_time"]}',
    ]
    if activity['location']:
        lines.append(f'LOCATION:{activity["location"]}')
    if activity['description']:
        lines.append(f'DESCRIPTION:{activity["description"]}')
    lines.append(VEVENT_END)
    return lines


def export_training_plan_ics(activities: list[dict[str, Any]]) -> str:
    """导出训练计划为 ICS 文本。"""
    normalized = [_validate_activity(activity) for activity in activities]
    normalized.sort(key=lambda item: item['start_time'])

    lines = [VCALENDAR_HEADER, VCALENDAR_VERSION, VCALENDAR_PRODID, VCALENDAR_CALSCALE, VCALENDAR_METHOD]
    for index, activity in enumerate(normalized, start=1):
        lines.extend(_event_lines(activity, index))
    lines.append(VCALENDAR_END)
    return CRLF.join(lines) + CRLF
