from __future__ import annotations

import hashlib
from typing import Any

MAX_REASONABLE_DISTANCE_KM = 100.0
MIN_REASONABLE_PACE_SECONDS_PER_KM = 150.0
MAX_REASONABLE_PACE_SECONDS_PER_KM = 900.0


def _text(value: Any) -> str:
    """把任意输入转换为去空白文本。

    Args:
        value: 原始输入值。

    Returns:
        去除前后空白后的文本。
    """
    if value is None:
        return ''
    return str(value).strip()


def _as_float(value: Any) -> float | None:
    """把输入安全转换为浮点数。

    Args:
        value: 原始输入值。

    Returns:
        转换成功的浮点数，失败时返回 None。
    """
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _track_key(value: Any) -> str:
    """生成 GPS 轨迹去重键。

    Args:
        value: GPS 轨迹原始值。

    Returns:
        轨迹摘要键；空轨迹返回空字符串。
    """
    text = _text(value)
    if text in {'', '[]', 'null', 'None'}:
        return ''
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _row_value(row: dict[str, Any], mapping: dict[str, str], field: str) -> Any:
    """按字段映射读取行值。

    Args:
        row: 导入数据行。
        mapping: 标准字段到原始字段名的映射。
        field: 标准字段名。

    Returns:
        行内对应值，缺失时返回 None。
    """
    key = mapping.get(field)
    if not key:
        return None
    return row.get(key)


def _anomaly(row_number: int, code: str, severity: str, suggestion: str, message: str) -> dict[str, Any]:
    """构造统一异常项。

    Args:
        row_number: 数据行号。
        code: 中文错误码。
        severity: 严重级别。
        suggestion: 可修复建议。
        message: 可读说明。

    Returns:
        统一异常字典。
    """
    return {
        'row': row_number,
        'code': code,
        'severity': severity,
        'message': message,
        'suggestion': suggestion,
    }


def _pace_anomaly(row_number: int, distance_km: float | None, duration_seconds: float | None) -> dict[str, Any] | None:
    """检查配速异常。

    Args:
        row_number: 数据行号。
        distance_km: 距离公里数。
        duration_seconds: 用时秒数。

    Returns:
        异常项或 None。
    """
    if distance_km is None or duration_seconds is None or distance_km <= 0 or duration_seconds <= 0:
        return None
    pace = duration_seconds / distance_km
    if pace < MIN_REASONABLE_PACE_SECONDS_PER_KM or pace > MAX_REASONABLE_PACE_SECONDS_PER_KM:
        return _anomaly(
            row_number,
            '异常配速',
            '警告',
            '请核对距离和用时，必要时改为手动确认后再导入',
            f'平均配速约为每公里 {pace:.0f} 秒，超出常见跑步范围',
        )
    return None


def precheck_running_data_anomalies(rows: list[dict[str, Any]], mapping: dict[str, str]) -> dict[str, Any]:
    """预检跑步数据导入异常。

    Args:
        rows: 已解析的导入数据行。
        mapping: 标准字段到原始字段名的映射。

    Returns:
        包含汇总和异常列表的字典。
    """
    anomalies: list[dict[str, Any]] = []
    track_rows: dict[str, list[int]] = {}
    for index, row in enumerate(rows, start=1):
        start_time = _text(_row_value(row, mapping, 'start_time'))
        distance = _as_float(_row_value(row, mapping, 'distance_km'))
        duration = _as_float(_row_value(row, mapping, 'duration_seconds'))
        track = _row_value(row, mapping, 'gps_track')
        track_key = _track_key(track)

        if not start_time:
            anomalies.append(_anomaly(index, '缺失时间', '阻断', '补充开始时间后再导入', '跑步记录缺少开始时间'))
        if distance is not None and distance > MAX_REASONABLE_DISTANCE_KM:
            anomalies.append(_anomaly(index, '超长距离', '警告', '请确认是否为多段记录合并，必要时拆分后导入', f'距离 {distance:g} 公里超过单次跑步常见范围'))
        if not track_key:
            anomalies.append(_anomaly(index, '空GPS点', '提示', '可补充轨迹文件；若为室内跑，请在前端标记为无轨迹导入', 'GPS 轨迹为空'))
        else:
            track_rows.setdefault(track_key, []).append(index)
        pace_item = _pace_anomaly(index, distance, duration)
        if pace_item is not None:
            anomalies.append(pace_item)

    for duplicate_rows in track_rows.values():
        if len(duplicate_rows) < 2:
            continue
        rows_text = '、'.join(str(row_number) for row_number in duplicate_rows)
        for row_number in duplicate_rows:
            anomalies.append(
                _anomaly(
                    row_number,
                    '重复轨迹',
                    '阻断',
                    '请删除重复记录或确认只保留其中一条轨迹',
                    f'第 {rows_text} 行使用了相同 GPS 轨迹',
                )
            )

    blocking_count = sum(1 for item in anomalies if item['severity'] == '阻断')
    return {
        'summary': {
            'total_rows': len(rows),
            'anomaly_count': len(anomalies),
            'blocking_count': blocking_count,
            'can_import': blocking_count == 0,
        },
        'anomalies': sorted(anomalies, key=lambda item: (int(item['row']), str(item['code']))),
    }
