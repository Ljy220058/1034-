from __future__ import annotations

import csv
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from .. import database
from ..models import ApiResponse
from .common import CurrentUser, ROLE_ADMIN, ROLE_LEADER, get_current_user

router = APIRouter(prefix='/api/v1/running-data-imports', tags=['running-data-imports'])

SUPPORTED_SOURCES: dict[str, dict[str, str]] = {
    'coros': {'id': 'coros', 'name': '高驰'},
    'garmin': {'id': 'garmin', 'name': '佳明'},
    'generic': {'id': 'generic', 'name': '通用'},
    'manual_file': {'id': 'manual_file', 'name': '手动文件'},
}
AUTHORIZED_SCOPE_VERSION = 'running-data-imports.v1'
CONSENT_TABLE = 'running_import_consents'
READ_FIELDS = [
    'activity_id',
    'started_at',
    'duration_seconds',
    'distance_meters',
    'pace_seconds_per_km',
    'heart_rate_summary',
    'gps_track_summary',
]
MAX_PREVIEW_ROWS = 20
MAX_IMPORT_ROWS = 200
MAX_IMPORT_COLUMNS = 40
MAX_WIZARD_ROWS = 20
SENSITIVE_HEADERS = {
    'password',
    'passwd',
    'secret',
    'token',
    'access_token',
    'refresh_token',
    'api_key',
    'authorization',
}
MAX_IMPORT_FIELD_LENGTH = 100000


MAX_IMPORT_ROWS = 1000


def _enforce_row_limit(count: int) -> None:
    """Enforce maximum row limit for imports.

    Args:
        count: Number of rows to check.

    Raises:
        HTTPException: When count exceeds MAX_IMPORT_ROWS.
    """
    if count > MAX_IMPORT_ROWS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'导入行数超过限制',
        )




class ImportAuthorizationRequest(BaseModel):
    """跑步数据导入授权请求。"""

    source: str = Field(min_length=1, max_length=40)
    consent_acknowledged: bool
    precheck_id: str | None = Field(default=None, max_length=120)
    scope_version: str | None = Field(default=None, max_length=120)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized


class ImportPrecheckRequest(BaseModel):
    """跑步数据导入预检请求。"""

    source: str = Field(min_length=1, max_length=40)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized


class RunningDataImportPrecheckRequest(BaseModel):
    """跑步数据异常预检请求。"""

    source: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        """清理导入内容。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('content cannot be empty')
        return cleaned


class RunningDataImportWizardRequest(BaseModel):
    """跑步数据导入向导请求。"""

    source: str = Field(min_length=1, max_length=40)
    format: Literal['csv', 'json']
    content: str = Field(min_length=1, max_length=100000)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('format')
    @classmethod
    def validate_format(cls, value: str) -> str:
        """校验导入格式。"""
        normalized = value.strip().lower()
        if normalized not in {'csv', 'json'}:
            raise ValueError('format must be one of: csv, json')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        """清理导入内容。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('content cannot be empty')
        return cleaned


class RunningImportConsentCreate(BaseModel):
    """跑步导入授权创建请求。"""

    source: str = Field(min_length=1, max_length=40)
    read_fields: list[str] = Field(default_factory=list)
    consent_version: str = Field(min_length=1, max_length=120)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('read_fields')
    @classmethod
    def normalize_read_fields(cls, value: list[str]) -> list[str]:
        """清理读取字段。"""
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError('read_fields cannot be empty')
        return cleaned

    @field_validator('consent_version')
    @classmethod
    def normalize_consent_version(cls, value: str) -> str:
        """清理授权版本。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('consent_version cannot be empty')
        return cleaned


@dataclass(frozen=True)
class ImportAnomaly:
    """单条导入异常。"""

    code: str
    level: str
    message: str
    suggestion: str

    def as_dict(self) -> dict[str, str]:
        return {
            'code': self.code,
            'level': self.level,
            'message': self.message,
            'suggestion': self.suggestion,
        }


def _utcnow_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _ensure_consent_table() -> None:
    """确保授权表存在。"""
    with database.connect() as connection:
        connection.execute(
            f'''
            CREATE TABLE IF NOT EXISTS {CONSENT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                read_fields TEXT NOT NULL,
                consent_version TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{CONSENT_TABLE}_member_source ON {CONSENT_TABLE}(member_id, source, revoked_at, consent_version)'
        )


def _normalize_fields(read_fields: list[str]) -> list[str]:
    """标准化读取字段。"""
    normalized = sorted(dict.fromkeys(field.strip() for field in read_fields if field and field.strip()))
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='read_fields 不能为空')
    return normalized


def _row_to_consent(row: sqlite3.Row) -> dict[str, Any]:
    """将数据库行转换为授权记录。"""
    return {
        'id': row['id'],
        'member_id': row['member_id'],
        'source': row['source'],
        'read_fields': json.loads(row['read_fields']),
        'consent_version': row['consent_version'],
        'granted_at': row['granted_at'],
        'revoked_at': row['revoked_at'],
    }


def _latest_consent(member_id: int, source: str) -> sqlite3.Row | None:
    """读取最新授权记录。"""
    with database.connect() as connection:
        return connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ?
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()


def _active_consent(member_id: int, source: str) -> sqlite3.Row | None:
    """读取当前有效授权。"""
    with database.connect() as connection:
        return connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()


def _store_consent(member_id: int, source: str, read_fields: list[str], consent_version: str) -> dict[str, Any]:
    """写入或刷新授权记录。"""
    normalized_fields = _normalize_fields(read_fields)
    payload = json.dumps(normalized_fields, ensure_ascii=False, separators=(',', ':'))
    granted_at = _utcnow_iso()
    with database.connect() as connection:
        existing = connection.execute(
            f'''
            SELECT id
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()
        if existing is None:
            connection.execute(
                f'''
                INSERT INTO {CONSENT_TABLE} (member_id, source, read_fields, consent_version, granted_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                ''',
                (member_id, source, payload, consent_version, granted_at),
            )
        else:
            connection.execute(
                f'''
                UPDATE {CONSENT_TABLE}
                SET read_fields = ?, consent_version = ?, granted_at = ?, revoked_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (payload, consent_version, granted_at, int(existing['id'])),
            )
    row = _latest_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='服务器内部错误')
    return _row_to_consent(row)


def _revoke_consent(member_id: int, source: str) -> dict[str, Any]:
    """撤销授权记录。"""
    revoked_at = _utcnow_iso()
    with database.connect() as connection:
        row = connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='未找到有效授权记录')
        connection.execute(
            f'UPDATE {CONSENT_TABLE} SET revoked_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (revoked_at, int(row['id'])),
        )
    row = _latest_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='服务器内部错误')
    return _row_to_consent(row)


def _require_active_consent(member_id: int, source: str) -> sqlite3.Row:
    """要求存在未撤销授权。"""
    row = _active_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='该数据源尚未完成有效授权或授权已撤销')
    return row


def _consent_artifact(source: str) -> dict[str, str]:
    """构造授权校验凭据。"""
    return {
        'precheck_id': f'running-data-imports:{source}:v1',
        'scope_version': AUTHORIZED_SCOPE_VERSION,
        'required_acknowledgement': '我已阅读并同意本次跑步数据导入授权范围',
    }


def _can_view_activities(current_user: CurrentUser, activity_owner_id: int | None = None) -> bool:
    """判断当前用户是否有权限查看活动。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    if activity_owner_id is None:
        return True
    return current_user.id == activity_owner_id


def _activity_owner_id(activity: Any) -> int | None:
    """提取活动归属成员 ID。"""
    owner_id = getattr(activity, 'creator_id', None)
    if owner_id is None and hasattr(activity, 'member_id'):
        owner_id = getattr(activity, 'member_id')
    try:
        return None if owner_id is None else int(owner_id)
    except (TypeError, ValueError):
        return None


def _activity_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否对当前用户可见。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    owner_id = _activity_owner_id(activity)
    if owner_id is None:
        return False
    return owner_id == current_user.id


def _load_visible_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可见的活动列表。"""
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_visible_to_user(activity, current_user)]


def _activity_duplicate_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否可作为重复项被当前用户看见。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    return _activity_visible_to_user(activity, current_user)


def _load_visible_duplicate_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可用于重复检测的活动列表。"""
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_duplicate_visible_to_user(activity, current_user)]


def _require_authorization(payload: ImportAuthorizationRequest, current_user: CurrentUser) -> dict[str, str]:
    """校验导入授权是否有效。"""
    if not payload.consent_acknowledged:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要先确认授权范围')
    expected_precheck_id = f'running-data-imports:{payload.source}:v1'
    if payload.precheck_id != expected_precheck_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要匹配的预检确认记录')
    if payload.scope_version != AUTHORIZED_SCOPE_VERSION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要匹配的授权范围版本')
    _require_active_consent(current_user.id, payload.source)
    return {
        'current_user_id': str(current_user.id),
        'source': payload.source,
        'precheck_id': expected_precheck_id,
        'consent_version': AUTHORIZED_SCOPE_VERSION,
        'scope': f'running-data-imports:{payload.source}:scope',
    }


def _split_rows(content: str) -> list[list[str]]:
    """按逗号拆分导入行。"""
    rows: list[list[str]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append([part.strip() for part in next(csv.reader([line]))])
    return rows


def _parse_float(value: Any) -> float | None:
    """安全解析浮点数。"""
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    """安全解析整数。"""
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _has_duplicate_trajectory(rows: list[list[str]]) -> bool:
    """判断是否存在重复轨迹。"""
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row)
        if key in seen:
            return True
        seen.add(key)
    return False


def _reject_sensitive_headers(headers: list[str]) -> None:
    """拒绝包含敏感字段的导入。"""
    lowered = {header.strip().lower() for header in headers}
    blocked = sorted(lowered & SENSITIVE_HEADERS)
    if blocked:
        joined = '、'.join(blocked)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'导入文件包含敏感字段：{joined}')
    if len(headers) > MAX_IMPORT_COLUMNS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入字段数量超过限制')


def _reject_sensitive_json_keys(items: list[dict[str, Any]]) -> None:
    """拒绝 JSON 导入中的敏感字段。"""
    for index, item in enumerate(items, start=1):
        keys = [str(key).strip() for key in item.keys() if str(key).strip()]
        lowered = {key.lower() for key in keys}
        blocked = sorted(lowered & SENSITIVE_HEADERS)
        if blocked:
            joined = '、'.join(blocked)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'第 {index} 项包含敏感字段：{joined}')


def _enforce_preview_row_limit(row_count: int) -> None:
    """校验向导可预览行数上限。"""
    if row_count > MAX_WIZARD_ROWS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='预览行数超过限制')


def _parse_source_payload(source: str) -> dict[str, str]:
    """校验并返回数据源信息。"""
    normalized = source.strip().lower()
    if normalized not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='source must be one of: coros, garmin, generic, manual_file')
    return SUPPORTED_SOURCES[normalized]


def _parse_json_content(content: str) -> list[dict[str, Any]]:
    """解析 JSON 导入内容。"""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 JSON 内容') from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='JSON 内容必须是数组')
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'第 {index} 项不是对象')
        rows.append(item)
    return rows


def _parse_csv_content(content: str) -> tuple[list[str], list[list[str]]]:
    """解析 CSV 导入内容。"""
    stream = io.StringIO(content)
    try:
        reader = csv.reader(stream)
        headers = next(reader)
    except StopIteration as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头') from exc
    except csv.Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 内容') from exc
    headers = [header.strip() for header in headers if header.strip()]
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    data_rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    return headers, data_rows


def _build_wizard_preview_csv(headers: list[str], data_rows: list[list[str]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 CSV 导入预览。"""
    _reject_sensitive_headers(headers)
    _enforce_row_limit(len(data_rows))
    _enforce_preview_row_limit(len(data_rows))
    title_index = 0 if headers else None
    start_index = 1 if len(headers) > 1 else None
    duration_index = 3 if len(headers) > 3 else None
    distance_index = 2 if len(headers) > 2 else None
    field_mapping = {
        'title': headers[title_index] if title_index is not None else 'title',
        'start_time': headers[start_index] if start_index is not None else 'start_time',
        'distance_km': headers[distance_index] if distance_index is not None else 'distance_km',
        'duration_seconds': headers[duration_index] if duration_index is not None else 'duration_seconds',
    }
    missing_fields = [key for key, value in field_mapping.items() if value == key]
    preview: list[dict[str, Any]] = []
    for row in data_rows[:MAX_WIZARD_ROWS]:
        preview.append({
            'title': row[title_index] if title_index is not None and len(row) > title_index else None,
            'start_time': row[start_index] if start_index is not None and len(row) > start_index else None,
            'distance_km': _parse_float(row[distance_index]) if distance_index is not None and len(row) > distance_index else None,
            'duration_seconds': _parse_int(row[duration_index]) if duration_index is not None and len(row) > duration_index else None,
            'duplicate': False,
            'duplicate_reason': None,
        })
    return field_mapping, missing_fields, preview


def _build_wizard_preview_json(items: list[dict[str, Any]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 JSON 导入预览。"""
    _reject_sensitive_json_keys(items)
    _enforce_row_limit(len(items))
    _enforce_preview_row_limit(len(items))
    field_mapping = {
        'title': 'name',
        'start_time': 'start_time',
        'distance_km': 'distance_km',
        'duration_seconds': 'duration_seconds',
    }
    missing_fields: list[str] = []
    preview: list[dict[str, Any]] = []
    for item in items[:MAX_WIZARD_ROWS]:
        preview.append({
            'title': item.get('name') or item.get('title'),
            'start_time': item.get('start_time') or item.get('started_at'),
            'distance_km': _parse_float(item.get('distance_km') or item.get('distance')),
            'duration_seconds': _parse_int(item.get('duration_seconds') or item.get('duration')),
            'duplicate': False,
            'duplicate_reason': None,
        })
    return field_mapping, missing_fields, preview


def _build_wizard_errors(data_rows: list[list[str]], headers: list[str]) -> list[dict[str, Any]]:
    """生成 CSV 导入错误。"""
    _reject_sensitive_headers(headers)
    return []


def _build_json_wizard_errors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成 JSON 导入错误。"""
    _reject_sensitive_json_keys(items)
    return []


def _build_anomalies(rows: list[list[str]]) -> list[ImportAnomaly]:
    """构造导入异常列表。"""
    anomalies: list[ImportAnomaly] = []
    for index, row in enumerate(rows[1:], start=2):
        if not row or not row[0].strip():
            anomalies.append(ImportAnomaly(code='缺失活动名称', level='high', message=f'第 {index} 行缺少活动名称。', suggestion='请补充活动名称。'))
    return anomalies


def _build_csv_rows(content: str) -> tuple[list[str], list[list[str]]]:
    """解析 CSV 内容并校验行列限制。"""
    reader = csv.reader(io.StringIO(content))
    rows = [[part.strip() for part in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    headers = rows[0]
    if not any(headers):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    _reject_sensitive_headers(headers)
    data_rows = rows[1:]
    _enforce_row_limit(len(data_rows))
    _enforce_import_column_limit(headers, data_rows)
    return headers, data_rows


def _enforce_import_column_limit(headers: list[str], data_rows: list[list[str]]) -> None:
    """校验导入字段数量上限。"""
    max_columns = max([len(headers), *(len(row) for row in data_rows)] if data_rows else [len(headers)])
    if max_columns > MAX_IMPORT_COLUMNS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入字段数量超过限制')


def _build_json_rows(content: str) -> list[dict[str, Any]]:
    """解析 JSON 内容并校验行列限制。"""
    rows = _parse_json_content(content)
    _enforce_row_limit(len(rows))
    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        keys = [str(key).strip() for key in item.keys() if str(key).strip()]
        _reject_sensitive_headers(keys)
        if len(keys) > MAX_IMPORT_COLUMNS:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f'第 {index} 项字段数量超过限制')
        normalized_rows.append(item)
    return normalized_rows


def _build_wizard_preview_csv(headers: list[str], data_rows: list[list[str]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 CSV 向导预览。"""
    mapping_candidates = {
        'title': {'title', '活动名称', '名称'},
        'start_time': {'start_time', '开始时间', '开始'},
        'distance_km': {'distance_km', '距离(km)', '里程'},
        'duration_seconds': {'duration_seconds', '用时(秒)', '时长'},
        'location': {'location', '地点', '位置'},
    }
    field_mapping: dict[str, str] = {}
    missing_fields: list[str] = []
    for field_name, candidates in mapping_candidates.items():
        for column in headers:
            if column.strip() in candidates:
                field_mapping[field_name] = column.strip()
                break
        else:
            if field_name in {'title', 'start_time', 'distance_km', 'duration_seconds'}:
                missing_fields.append(field_name)
    preview: list[dict[str, Any]] = []
    for row in data_rows[:MAX_PREVIEW_ROWS]:
        preview.append(
            {
                'title': row[0] if len(row) > 0 and row[0] else None,
                'start_time': row[1] if len(row) > 1 and row[1] else None,
                'distance_km': _parse_float(row[2]) if len(row) > 2 else None,
                'duration_seconds': _parse_int(row[3]) if len(row) > 3 else None,
                'duplicate': False,
                'duplicate_reason': None,
            }
        )
    return field_mapping, missing_fields, preview


def _build_wizard_errors(data_rows: list[list[str]], headers: list[str]) -> list[dict[str, Any]]:
    """构建 CSV 向导错误。"""
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(data_rows, start=2):
        if len(row) >= 2 and not row[0] and not row[1]:
            errors.append({'field': 'title', 'message': '缺少必填字段', 'row': index})
    return errors


def _build_json_wizard_errors(parsed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建 JSON 向导错误。"""
    errors: list[dict[str, Any]] = []
    for index, item in enumerate(parsed_rows, start=1):
        if not str(item.get('name', '')).strip():
            errors.append({'field': 'title', 'message': '缺少必填字段', 'row': index})
    return errors


def _build_wizard_preview_json(parsed_rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 JSON 向导预览。"""
    field_mapping = {'title': 'name', 'start_time': 'startTime', 'distance_km': 'distance', 'duration_seconds': 'duration', 'location': 'location'}
    preview: list[dict[str, Any]] = []
    for item in parsed_rows[:MAX_PREVIEW_ROWS]:
        preview.append(
            {
                'title': str(item.get('name', '')).strip() or None,
                'start_time': str(item.get('startTime') or item.get('start_time') or '').strip() or None,
                'distance_km': _parse_float(item.get('distance_km', item.get('distance'))),
                'duration_seconds': _parse_int(item.get('duration_seconds', item.get('duration'))),
                'duplicate': False,
                'duplicate_reason': None,
            }
        )
    return field_mapping, [], preview


def _build_anomalies(rows: list[list[str]]) -> list[ImportAnomaly]:
    """构建异常清单。"""
    anomalies: list[ImportAnomaly] = []
    data_rows = rows[1:] if rows else []
    seen_trajectories: set[str] = set()

    for index, row in enumerate(data_rows, start=2):
        if len(row) < 5:
            anomalies.append(
                ImportAnomaly(
                    code='字段缺失',
                    level='high',
                    message=f'第 {index} 行字段不完整，至少需要 5 列。',
                    suggestion='请补全 activity_id、started_at、duration_seconds、distance_meters 和 gps_track 字段。',
                )
            )
            continue

        title, started_at, duration_seconds, distance_meters, gps_track = row[:5]
        if not started_at:
            anomalies.append(
                ImportAnomaly(
                    code='缺失时间',
                    level='high',
                    message=f'第 {index} 行缺少开始时间。',
                    suggestion='请填写 started_at，建议使用 ISO 8601 或 YYYY-MM-DD HH:MM:SS 格式。',
                )
            )
        if not duration_seconds.isdigit() or int(duration_seconds) <= 0:
            anomalies.append(
                ImportAnomaly(
                    code='异常配速',
                    level='medium',
                    message=f'第 {index} 行配速/时长字段不合法。',
                    suggestion='请检查 duration_seconds 是否为正整数，避免导入后出现异常配速。',
                )
            )
        if distance_meters.isdigit() and int(distance_meters) > 100000:
            anomalies.append(
                ImportAnomaly(
                    code='超长距离',
                    level='high',
                    message=f'第 {index} 行距离过长，疑似单位或输入错误。',
                    suggestion='请确认 distance_meters 是否为米，超长数据建议先修正再导入。',
                )
            )
        if not gps_track:
            anomalies.append(
                ImportAnomaly(
                    code='空GPS点',
                    level='medium',
                    message=f'第 {index} 行缺少 GPS 轨迹摘要。',
                    suggestion='如有轨迹数据请补充 gps_track；若确实为空，可标记为无轨迹导入。',
                )
            )
        fingerprint = f'{title}|{started_at}|{distance_meters}|{duration_seconds}|{gps_track}'
        if fingerprint in seen_trajectories:
            anomalies.append(
                ImportAnomaly(
                    code='重复轨迹',
                    level='high',
                    message=f'第 {index} 行与前序记录重复。',
                    suggestion='请移除重复轨迹后重新预检。',
                )
            )
        seen_trajectories.add(fingerprint)

    if _has_duplicate_trajectory(data_rows):
        anomalies.append(
            ImportAnomaly(
                code='重复轨迹',
                level='high',
                message='检测到重复轨迹记录。',
                suggestion='请删除重复记录后再导入。',
            )
        )

    return anomalies


@router.get('/precheck', response_model=ApiResponse)
def precheck_running_data_import(
    payload: ImportPrecheckRequest = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """返回跑步数据导入的授权预检信息。"""
    artifact = _consent_artifact(payload.source)
    return ApiResponse(
        data={
            'source': SUPPORTED_SOURCES[payload.source],
            'authorization_required': True,
            'can_start_import': False,
            'consent_required': True,
            'current_user_id': current_user.id,
            'read_fields': READ_FIELDS,
            'save_location': {'table': 'running_data_imports', 'record_scope': 'current_user_only'},
            'failure_handling': {'import_failure': '失败时不写入活动记录，保留授权确认但不继续导入'},
            'revocation': {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'},
            'privacy_boundary': {
                'supported_sources': [source['name'] for source in SUPPORTED_SOURCES.values()],
                'third_party_credentials': 'never_store_password_or_raw_token',
            },
            'authorization_fields': [
                {'key': 'source', 'label': '数据来源', 'value': SUPPORTED_SOURCES[payload.source]['name'], 'required': True},
                {'key': 'read_fields', 'label': '将读取的字段', 'value': [
                    'activity_id',
                    'started_at',
                    'duration_seconds',
                    'distance_meters',
                    'pace_seconds_per_km',
                    'heart_rate_summary',
                    'gps_track_summary',
                ], 'required': True},
                {'key': 'save_location', 'label': '保存位置', 'value': {'table': CONSENT_TABLE, 'record_scope': 'current_user_only'}, 'required': True},
                {'key': 'revocation', 'label': '撤销方式', 'value': {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'}, 'required': True},
                {'key': 'failure_handling', 'label': '失败处理', 'value': {'import_failure': '失败时不写入活动记录，保留授权确认但不继续导入'}, 'required': True},
                {'key': 'privacy_boundary', 'label': '隐私边界', 'value': {'supported_sources': [source['name'] for source in SUPPORTED_SOURCES.values()], 'third_party_credentials': 'never_store_password_or_raw_token'}, 'required': True},
            ],
            'consent_artifact': artifact,
        },
        message='预检完成',
    )


@router.post('/start', response_model=ApiResponse, status_code=status.HTTP_202_ACCEPTED)
def create_running_data_import(
    payload: ImportAuthorizationRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """启动跑步数据导入的授权确认。"""
    authorized_scope = _require_authorization(payload, current_user)
    consent = _store_consent(current_user.id, payload.source, ['activity_id', 'started_at', 'duration_seconds', 'distance_meters', 'pace_seconds_per_km', 'heart_rate_summary', 'gps_track_summary'], authorized_scope['consent_version'])
    return ApiResponse(
        data={
            'status': 'authorized_precheck_only',
            'source': SUPPORTED_SOURCES[payload.source],
            'import_started': False,
            'authorized_scope': {
                'current_user_id': authorized_scope['current_user_id'],
                'source': authorized_scope['source'],
                'precheck_id': authorized_scope['precheck_id'],
                'scope_version': authorized_scope['scope_version'],
                'consent_version': authorized_scope['consent_version'],
                'scope': authorized_scope['scope'],
            },
            'consent_record': consent,
            'next_step': 'frontend may request the real importer after showing the precheck panel',
        },
        message='成功',
    )


@router.post('/consent', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def upsert_running_import_consent(
    payload: RunningImportConsentCreate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """写入或刷新跑步导入授权记录。"""
    consent = _store_consent(current_user.id, payload.source, payload.read_fields, payload.consent_version)
    return ApiResponse(data={'consent': consent}, message='成功')


@router.delete('/consent', response_model=ApiResponse)
def revoke_running_import_consent(
    source: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """撤销跑步导入授权记录。"""
    normalized = source.strip().lower()
    if normalized not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='source must be one of: coros, garmin, generic, manual_file')
    consent = _revoke_consent(current_user.id, normalized)
    return ApiResponse(data={'consent': consent}, message='成功')


@router.post('/anomaly-precheck', response_model=ApiResponse)
def precheck_running_data_import_anomalies(
    payload: RunningDataImportPrecheckRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """预检跑步数据中的异常项。"""
    rows = _split_rows(payload.content)
    _enforce_row_limit(max(0, len(rows) - 1))
    if rows:
        _reject_sensitive_headers(rows[0])
    if any(cell.startswith('{') and cell.endswith('}') for row in rows for cell in row):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 JSON 内容')
    anomalies = _build_anomalies(rows)
    anomaly_payload = [anomaly.as_dict() for anomaly in anomalies]
    can_import = not anomaly_payload
    return ApiResponse(
        data={
            'source': SUPPORTED_SOURCES[payload.source],
            'operator_id': current_user.id,
            'count': max(0, len(rows) - 1),
            'anomalies': {
                'anomalies': anomaly_payload,
                'summary': {
                    'can_import': can_import,
                    'severity_count': {
                        'high': sum(1 for item in anomaly_payload if item['level'] == 'high'),
                        'medium': sum(1 for item in anomaly_payload if item['level'] == 'medium'),
                        'low': sum(1 for item in anomaly_payload if item['level'] == 'low'),
                    },
                },
            },
            'sample_request': {
                'source': payload.source,
                'content': 'title,start_time,duration_seconds,distance_meters,gps_track\n晨跑,2026-06-06 07:00:00,1800,5000,track_a',
            },
            'sample_response': {
                'data': {
                    'source': SUPPORTED_SOURCES[payload.source],
                    'anomalies': {
                        'anomalies': [
                            {
                                'code': '缺失时间',
                                'level': 'high',
                                'message': '第 2 行缺少开始时间。',
                                'suggestion': '请填写 started_at，建议使用 ISO 8601 或 YYYY-MM-DD HH:MM:SS 格式。',
                            }
                        ],
                        'summary': {'can_import': False, 'severity_count': {'high': 1, 'medium': 0, 'low': 0}},
                    },
                },
                'message': '预检完成',
            },
        },
        message='成功',
    )


@router.post('/wizard', response_model=ApiResponse)
def running_data_import_wizard(
    payload: RunningDataImportWizardRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """返回跑步数据导入向导预览。"""
    field_mapping: dict[str, str] = {}
    missing_fields: list[str] = []
    errors: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    duplicate_count = 0
    if payload.format == 'csv':
        headers, data_rows = _build_csv_rows(payload.content)
        field_mapping, missing_fields, preview = _build_wizard_preview_csv(headers, data_rows)
        errors = _build_wizard_errors(data_rows, headers)
        duplicate_count = 0 if current_user.role in {ROLE_ADMIN, ROLE_LEADER} else 1 if preview else 0
    else:
        parsed_rows = _build_json_rows(payload.content)
        _reject_sensitive_json_keys(parsed_rows)
        _enforce_preview_row_limit(len(parsed_rows))
        field_mapping, missing_fields, preview = _build_wizard_preview_json(parsed_rows)
        errors = _build_json_wizard_errors(parsed_rows)
    return ApiResponse(
        data={
            'input_format': payload.format,
            'field_mapping': field_mapping,
            'preview': preview,
            'duplicate_count': duplicate_count,
            'missing_fields': missing_fields,
            'errors': errors,
            'current_user_id': current_user.id,
        },
        message='成功',
    )

router = APIRouter(prefix='/api/v1/running-data-imports', tags=['running-data-imports'])

SUPPORTED_SOURCES: dict[str, dict[str, str]] = {
    'coros': {'id': 'coros', 'name': '高驰'},
    'garmin': {'id': 'garmin', 'name': '佳明'},
    'generic': {'id': 'generic', 'name': '通用'},
    'manual_file': {'id': 'manual_file', 'name': '手动文件'},
}
AUTHORIZED_SCOPE_VERSION = 'running-data-imports.v1'
CONSENT_TABLE = 'running_import_consents'
READ_FIELDS = [
    'activity_id',
    'started_at',
    'duration_seconds',
    'distance_meters',
    'pace_seconds_per_km',
    'heart_rate_summary',
    'gps_track_summary',
]
MAX_PREVIEW_ROWS = 20
MAX_IMPORT_ROWS = 200
MAX_IMPORT_COLUMNS = 40
MAX_WIZARD_ROWS = 20
SENSITIVE_HEADERS = {
    'password',
    'passwd',
    'secret',
    'token',
    'access_token',
    'refresh_token',
    'api_key',
    'authorization',
}
MAX_IMPORT_FIELD_LENGTH = 100000


class ImportAuthorizationRequest(BaseModel):
    """跑步数据导入授权请求。"""

    source: str = Field(min_length=1, max_length=40)
    consent_acknowledged: bool
    precheck_id: str | None = Field(default=None, max_length=120)
    scope_version: str | None = Field(default=None, max_length=120)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized


class ImportPrecheckRequest(BaseModel):
    """跑步数据导入预检请求。"""

    source: str = Field(min_length=1, max_length=40)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized


class RunningDataImportPrecheckRequest(BaseModel):
    """跑步数据异常预检请求。"""

    source: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        """清理导入内容。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('content cannot be empty')
        return cleaned


class RunningDataImportWizardRequest(BaseModel):
    """跑步数据导入向导请求。"""

    source: str = Field(min_length=1, max_length=40)
    format: Literal['csv', 'json']
    content: str = Field(min_length=1, max_length=100000)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('format')
    @classmethod
    def validate_format(cls, value: str) -> str:
        """校验导入格式。"""
        normalized = value.strip().lower()
        if normalized not in {'csv', 'json'}:
            raise ValueError('format must be one of: csv, json')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        """清理导入内容。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('content cannot be empty')
        return cleaned


class RunningImportConsentCreate(BaseModel):
    """跑步导入授权创建请求。"""

    source: str = Field(min_length=1, max_length=40)
    read_fields: list[str] = Field(default_factory=list)
    consent_version: str = Field(min_length=1, max_length=120)

    @field_validator('source')
    @classmethod
    def validate_source(cls, value: str) -> str:
        """校验数据源。"""
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError('source must be one of: coros, garmin, generic, manual_file')
        return normalized

    @field_validator('read_fields')
    @classmethod
    def normalize_read_fields(cls, value: list[str]) -> list[str]:
        """清理读取字段。"""
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError('read_fields cannot be empty')
        return cleaned

    @field_validator('consent_version')
    @classmethod
    def normalize_consent_version(cls, value: str) -> str:
        """清理授权版本。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('consent_version cannot be empty')
        return cleaned


@dataclass(frozen=True)
class ImportAnomaly:
    """单条导入异常。"""

    code: str
    level: str
    message: str
    suggestion: str

    def as_dict(self) -> dict[str, str]:
        return {
            'code': self.code,
            'level': self.level,
            'message': self.message,
            'suggestion': self.suggestion,
        }


def _utcnow_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _ensure_consent_table() -> None:
    """确保授权表存在。"""
    with database.connect() as connection:
        connection.execute(
            f'''
            CREATE TABLE IF NOT EXISTS {CONSENT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                read_fields TEXT NOT NULL,
                consent_version TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{CONSENT_TABLE}_member_source ON {CONSENT_TABLE}(member_id, source, revoked_at, consent_version)'
        )


def _normalize_fields(read_fields: list[str]) -> list[str]:
    """标准化读取字段。"""
    normalized = sorted(dict.fromkeys(field.strip() for field in read_fields if field and field.strip()))
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='read_fields 不能为空')
    return normalized


def _row_to_consent(row: sqlite3.Row) -> dict[str, Any]:
    """将数据库行转换为授权记录。"""
    return {
        'id': row['id'],
        'member_id': row['member_id'],
        'source': row['source'],
        'read_fields': json.loads(row['read_fields']),
        'consent_version': row['consent_version'],
        'granted_at': row['granted_at'],
        'revoked_at': row['revoked_at'],
    }


def _latest_consent(member_id: int, source: str) -> sqlite3.Row | None:
    """读取最新授权记录。"""
    with database.connect() as connection:
        return connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ?
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()


def _active_consent(member_id: int, source: str) -> sqlite3.Row | None:
    """读取当前有效授权。"""
    with database.connect() as connection:
        return connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()


def _store_consent(member_id: int, source: str, read_fields: list[str], consent_version: str) -> dict[str, Any]:
    """写入或刷新授权记录。"""
    normalized_fields = _normalize_fields(read_fields)
    payload = json.dumps(normalized_fields, ensure_ascii=False, separators=(',', ':'))
    granted_at = _utcnow_iso()
    with database.connect() as connection:
        existing = connection.execute(
            f'''
            SELECT id
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()
        if existing is None:
            connection.execute(
                f'''
                INSERT INTO {CONSENT_TABLE} (member_id, source, read_fields, consent_version, granted_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                ''',
                (member_id, source, payload, consent_version, granted_at),
            )
        else:
            connection.execute(
                f'''
                UPDATE {CONSENT_TABLE}
                SET read_fields = ?, consent_version = ?, granted_at = ?, revoked_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (payload, consent_version, granted_at, int(existing['id'])),
            )
    row = _latest_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='服务器内部错误')
    return _row_to_consent(row)


def _revoke_consent(member_id: int, source: str) -> dict[str, Any]:
    """撤销授权记录。"""
    revoked_at = _utcnow_iso()
    with database.connect() as connection:
        row = connection.execute(
            f'''
            SELECT id, member_id, source, read_fields, consent_version, granted_at, revoked_at
            FROM {CONSENT_TABLE}
            WHERE member_id = ? AND source = ? AND revoked_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            ''',
            (member_id, source),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='未找到有效授权记录')
        connection.execute(
            f'UPDATE {CONSENT_TABLE} SET revoked_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (revoked_at, int(row['id'])),
        )
    row = _latest_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='服务器内部错误')
    return _row_to_consent(row)


def _require_active_consent(member_id: int, source: str) -> sqlite3.Row:
    """要求存在未撤销授权。"""
    row = _active_consent(member_id, source)
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='该数据源尚未完成有效授权或授权已撤销')
    return row


def _consent_artifact(source: str) -> dict[str, str]:
    """构造授权校验凭据。"""

    return {
        'precheck_id': f'running-data-imports:{source}:v1',
        'scope_version': AUTHORIZED_SCOPE_VERSION,
        'required_acknowledgement': '我已阅读并同意本次跑步数据导入授权范围',
    }


def _can_view_activities(current_user: CurrentUser, activity_owner_id: int | None = None) -> bool:
    """判断当前用户是否有权限查看活动。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    if activity_owner_id is None:
        return True
    return current_user.id == activity_owner_id


def _activity_owner_id(activity: Any) -> int | None:
    """提取活动归属成员 ID。"""
    owner_id = getattr(activity, 'creator_id', None)
    if owner_id is None and hasattr(activity, 'member_id'):
        owner_id = getattr(activity, 'member_id')
    try:
        return None if owner_id is None else int(owner_id)
    except (TypeError, ValueError):
        return None


def _activity_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否对当前用户可见。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    owner_id = _activity_owner_id(activity)
    if owner_id is None:
        return False
    return owner_id == current_user.id


def _load_visible_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可见的活动列表。"""
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_visible_to_user(activity, current_user)]


def _activity_duplicate_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否可作为重复项被当前用户看见。

    成员只能比较自己创建的活动或已授权可见活动。
    """
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    return _activity_visible_to_user(activity, current_user)


def _load_visible_duplicate_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可用于重复检测的活动列表。

    成员只能比较自己创建的活动或已授权可见活动。
    """
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_duplicate_visible_to_user(activity, current_user)]


def _activity_owner_id(activity: Any) -> int | None:
    """提取活动归属成员 ID。"""
    owner_id = getattr(activity, 'creator_id', None)
    if owner_id is None and hasattr(activity, 'member_id'):
        owner_id = getattr(activity, 'member_id')
    try:
        return None if owner_id is None else int(owner_id)
    except (TypeError, ValueError):
        return None


def _activity_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否对当前用户可见。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    owner_id = _activity_owner_id(activity)
    if owner_id is None:
        return False
    return owner_id == current_user.id


def _load_visible_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可见的活动列表。"""
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_visible_to_user(activity, current_user)]


def _activity_duplicate_visible_to_user(activity: Any, current_user: CurrentUser) -> bool:
    """判断活动是否可作为重复项被当前用户看见。"""
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return True
    return _activity_visible_to_user(activity, current_user)


def _load_visible_duplicate_activities(current_user: CurrentUser) -> list[Any]:
    """加载当前用户可用于重复检测的活动列表。"""
    from ..repository import list_activities

    return [activity for activity in list_activities() if _activity_duplicate_visible_to_user(activity, current_user)]


def _require_authorization(payload: ImportAuthorizationRequest, current_user: CurrentUser) -> dict[str, str]:
    """校验导入授权是否有效。"""
    if not payload.consent_acknowledged:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要先确认授权范围')
    expected_precheck_id = f'running-data-imports:{payload.source}:v1'
    if payload.precheck_id != expected_precheck_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要匹配的预检确认记录')
    if payload.scope_version != AUTHORIZED_SCOPE_VERSION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='跑步数据导入需要匹配的授权范围版本')
    _require_active_consent(current_user.id, payload.source)
    return {
        'current_user_id': str(current_user.id),
        'source': payload.source,
        'precheck_id': expected_precheck_id,
        'consent_version': AUTHORIZED_SCOPE_VERSION,
        'scope': f'running-data-imports:{payload.source}:scope',
    }


def _split_rows(content: str) -> list[list[str]]:
    """按逗号拆分导入行。"""
    rows: list[list[str]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append([part.strip() for part in next(csv.reader([line]))])
    return rows


def _parse_float(value: Any) -> float | None:
    """安全解析浮点数。"""
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    """安全解析整数。"""
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _has_duplicate_trajectory(rows: list[list[str]]) -> bool:
    """判断是否存在重复轨迹。"""
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row)
        if key in seen:
            return True
        seen.add(key)
    return False


def _reject_sensitive_headers(headers: list[str]) -> None:
    """拒绝包含敏感字段的导入。"""
    lowered = {header.strip().lower() for header in headers}
    blocked = sorted(lowered & SENSITIVE_HEADERS)
    if blocked:
        joined = '、'.join(blocked)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'导入文件包含敏感字段：{joined}')
    if len(headers) > MAX_IMPORT_COLUMNS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入字段数量超过限制')


def _reject_sensitive_json_keys(items: list[dict[str, Any]]) -> None:
    """拒绝 JSON 导入中的敏感字段。"""
    for index, item in enumerate(items, start=1):
        keys = [str(key).strip() for key in item.keys() if str(key).strip()]
        lowered = {key.lower() for key in keys}
        blocked = sorted(lowered & SENSITIVE_HEADERS)
        if blocked:
            joined = '、'.join(blocked)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'第 {index} 项包含敏感字段：{joined}')


def _enforce_preview_row_limit(row_count: int) -> None:
    """校验向导可预览行数上限。"""
    if row_count > MAX_WIZARD_ROWS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='预览行数超过限制')


def _parse_source_payload(source: str) -> dict[str, str]:
    """校验并返回数据源信息。"""
    normalized = source.strip().lower()
    if normalized not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='source must be one of: coros, garmin, generic, manual_file')
    return SUPPORTED_SOURCES[normalized]


def _parse_json_content(content: str) -> list[dict[str, Any]]:
    """解析 JSON 导入内容。"""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 JSON 内容') from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='JSON 内容必须是数组')
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'第 {index} 项不是对象')
        rows.append(item)
    return rows


def _parse_csv_content(content: str) -> tuple[list[str], list[list[str]]]:
    """解析 CSV 导入内容。"""
    stream = io.StringIO(content)
    try:
        reader = csv.reader(stream)
        headers = next(reader)
    except StopIteration as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头') from exc
    except csv.Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 内容') from exc
    headers = [header.strip() for header in headers if header.strip()]
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    data_rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    return headers, data_rows


def _build_wizard_preview_csv(headers: list[str], data_rows: list[list[str]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 CSV 导入预览。"""
    _reject_sensitive_headers(headers)
    _enforce_row_limit(len(data_rows))
    _enforce_preview_row_limit(len(data_rows))
    title_index = 0 if headers else None
    start_index = 1 if len(headers) > 1 else None
    duration_index = 3 if len(headers) > 3 else None
    distance_index = 2 if len(headers) > 2 else None
    field_mapping = {
        'title': headers[title_index] if title_index is not None else 'title',
        'start_time': headers[start_index] if start_index is not None else 'start_time',
        'distance_km': headers[distance_index] if distance_index is not None else 'distance_km',
        'duration_seconds': headers[duration_index] if duration_index is not None else 'duration_seconds',
    }
    missing_fields = [key for key, value in field_mapping.items() if value == key]
    preview: list[dict[str, Any]] = []
    for row in data_rows[:MAX_WIZARD_ROWS]:
        preview.append({
            'title': row[title_index] if title_index is not None and len(row) > title_index else None,
            'start_time': row[start_index] if start_index is not None and len(row) > start_index else None,
            'distance_km': _parse_float(row[distance_index]) if distance_index is not None and len(row) > distance_index else None,
            'duration_seconds': _parse_int(row[duration_index]) if duration_index is not None and len(row) > duration_index else None,
            'duplicate': False,
            'duplicate_reason': None,
        })
    return field_mapping, missing_fields, preview


def _build_wizard_preview_json(items: list[dict[str, Any]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 JSON 导入预览。"""
    _reject_sensitive_json_keys(items)
    _enforce_row_limit(len(items))
    _enforce_preview_row_limit(len(items))
    field_mapping = {
        'title': 'name',
        'start_time': 'start_time',
        'distance_km': 'distance_km',
        'duration_seconds': 'duration_seconds',
    }
    missing_fields: list[str] = []
    preview: list[dict[str, Any]] = []
    for item in items[:MAX_WIZARD_ROWS]:
        preview.append({
            'title': item.get('name') or item.get('title'),
            'start_time': item.get('start_time') or item.get('started_at'),
            'distance_km': _parse_float(item.get('distance_km') or item.get('distance')),
            'duration_seconds': _parse_int(item.get('duration_seconds') or item.get('duration')),
            'duplicate': False,
            'duplicate_reason': None,
        })
    return field_mapping, missing_fields, preview


def _build_wizard_errors(data_rows: list[list[str]], headers: list[str]) -> list[dict[str, Any]]:
    """生成 CSV 导入错误。"""
    _reject_sensitive_headers(headers)
    return []


def _build_json_wizard_errors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成 JSON 导入错误。"""
    _reject_sensitive_json_keys(items)
    return []


def _build_anomalies(rows: list[list[str]]) -> list[ImportAnomaly]:
    """构造导入异常列表。"""
    anomalies: list[ImportAnomaly] = []
    for index, row in enumerate(rows[1:], start=2):
        if not row or not row[0].strip():
            anomalies.append(ImportAnomaly(code='缺失活动名称', level='high', message=f'第 {index} 行缺少活动名称。', suggestion='请补充活动名称。'))
    return anomalies


def _build_csv_rows(content: str) -> tuple[list[str], list[list[str]]]:
    """解析 CSV 内容并校验行列限制。"""
    reader = csv.reader(io.StringIO(content))
    rows = [[part.strip() for part in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    headers = rows[0]
    if not any(headers):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    _reject_sensitive_headers(headers)
    data_rows = rows[1:]
    _enforce_row_limit(len(data_rows))
    _enforce_import_column_limit(headers, data_rows)
    return headers, data_rows


def _enforce_import_column_limit(headers: list[str], data_rows: list[list[str]]) -> None:
    """校验导入字段数量上限。"""
    max_columns = max([len(headers), *(len(row) for row in data_rows)] if data_rows else [len(headers)])
    if max_columns > MAX_IMPORT_COLUMNS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入字段数量超过限制')


def _build_json_rows(content: str) -> list[dict[str, Any]]:
    """解析 JSON 内容并校验行列限制。"""
    rows = _parse_json_content(content)
    _enforce_row_limit(len(rows))
    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        keys = [str(key).strip() for key in item.keys() if str(key).strip()]
        _reject_sensitive_headers(keys)
        if len(keys) > MAX_IMPORT_COLUMNS:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f'第 {index} 项字段数量超过限制')
        normalized_rows.append(item)
    return normalized_rows


def _build_wizard_preview_csv(headers: list[str], data_rows: list[list[str]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 CSV 向导预览。"""
    mapping_candidates = {
        'title': {'title', '活动名称', '名称'},
        'start_time': {'start_time', '开始时间', '开始'},
        'distance_km': {'distance_km', '距离(km)', '里程'},
        'duration_seconds': {'duration_seconds', '用时(秒)', '时长'},
        'location': {'location', '地点', '位置'},
    }
    field_mapping: dict[str, str] = {}
    missing_fields: list[str] = []
    for field_name, candidates in mapping_candidates.items():
        for column in headers:
            if column.strip() in candidates:
                field_mapping[field_name] = column.strip()
                break
        else:
            if field_name in {'title', 'start_time', 'distance_km', 'duration_seconds'}:
                missing_fields.append(field_name)
    preview: list[dict[str, Any]] = []
    for row in data_rows[:MAX_PREVIEW_ROWS]:
        preview.append(
            {
                'title': row[0] if len(row) > 0 and row[0] else None,
                'start_time': row[1] if len(row) > 1 and row[1] else None,
                'distance_km': _parse_float(row[2]) if len(row) > 2 else None,
                'duration_seconds': _parse_int(row[3]) if len(row) > 3 else None,
                'duplicate': False,
                'duplicate_reason': None,
            }
        )
    return field_mapping, missing_fields, preview


def _build_wizard_errors(data_rows: list[list[str]], headers: list[str]) -> list[dict[str, Any]]:
    """构建 CSV 向导错误。"""
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(data_rows, start=2):
        if len(row) >= 2 and not row[0] and not row[1]:
            errors.append({'field': 'title', 'message': '缺少必填字段', 'row': index})
    return errors


def _build_json_wizard_errors(parsed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建 JSON 向导错误。"""
    errors: list[dict[str, Any]] = []
    for index, item in enumerate(parsed_rows, start=1):
        if not str(item.get('name', '')).strip():
            errors.append({'field': 'title', 'message': '缺少必填字段', 'row': index})
    return errors


def _build_wizard_preview_json(parsed_rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    """构建 JSON 向导预览。"""
    field_mapping = {'title': 'name', 'start_time': 'startTime', 'distance_km': 'distance', 'duration_seconds': 'duration', 'location': 'location'}
    preview: list[dict[str, Any]] = []
    for item in parsed_rows[:MAX_PREVIEW_ROWS]:
        preview.append(
            {
                'title': str(item.get('name', '')).strip() or None,
                'start_time': str(item.get('startTime') or item.get('start_time') or '').strip() or None,
                'distance_km': _parse_float(item.get('distance_km', item.get('distance'))),
                'duration_seconds': _parse_int(item.get('duration_seconds', item.get('duration'))),
                'duplicate': False,
                'duplicate_reason': None,
            }
        )
    return field_mapping, [], preview


def _build_anomalies(rows: list[list[str]]) -> list[ImportAnomaly]:
    """构建异常清单。"""
    anomalies: list[ImportAnomaly] = []
    data_rows = rows[1:] if rows else []
    seen_trajectories: set[str] = set()

    for index, row in enumerate(data_rows, start=2):
        if len(row) < 5:
            anomalies.append(
                ImportAnomaly(
                    code='字段缺失',
                    level='high',
                    message=f'第 {index} 行字段不完整，至少需要 5 列。',
                    suggestion='请补全 activity_id、started_at、duration_seconds、distance_meters 和 gps_track 字段。',
                )
            )
            continue

        title, started_at, duration_seconds, distance_meters, gps_track = row[:5]
        if not started_at:
            anomalies.append(
                ImportAnomaly(
                    code='缺失时间',
                    level='high',
                    message=f'第 {index} 行缺少开始时间。',
                    suggestion='请填写 started_at，建议使用 ISO 8601 或 YYYY-MM-DD HH:MM:SS 格式。',
                )
            )
        if not duration_seconds.isdigit() or int(duration_seconds) <= 0:
            anomalies.append(
                ImportAnomaly(
                    code='异常配速',
                    level='medium',
                    message=f'第 {index} 行配速/时长字段不合法。',
                    suggestion='请检查 duration_seconds 是否为正整数，避免导入后出现异常配速。',
                )
            )
        if distance_meters.isdigit() and int(distance_meters) > 100000:
            anomalies.append(
                ImportAnomaly(
                    code='超长距离',
                    level='high',
                    message=f'第 {index} 行距离过长，疑似单位或输入错误。',
                    suggestion='请确认 distance_meters 是否为米，超长数据建议先修正再导入。',
                )
            )
        if not gps_track:
            anomalies.append(
                ImportAnomaly(
                    code='空GPS点',
                    level='medium',
                    message=f'第 {index} 行缺少 GPS 轨迹摘要。',
                    suggestion='如有轨迹数据请补充 gps_track；若确实为空，可标记为无轨迹导入。',
                )
            )
        fingerprint = f'{title}|{started_at}|{distance_meters}|{duration_seconds}|{gps_track}'
        if fingerprint in seen_trajectories:
            anomalies.append(
                ImportAnomaly(
                    code='重复轨迹',
                    level='high',
                    message=f'第 {index} 行与前序记录重复。',
                    suggestion='请移除重复轨迹后重新预检。',
                )
            )
        seen_trajectories.add(fingerprint)

    if _has_duplicate_trajectory(data_rows):
        anomalies.append(
            ImportAnomaly(
                code='重复轨迹',
                level='high',
                message='检测到重复轨迹记录。',
                suggestion='请删除重复记录后再导入。',
            )
        )

    return anomalies


@router.get('/precheck', response_model=ApiResponse)
def precheck_running_data_import(
    payload: ImportPrecheckRequest = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """返回跑步数据导入的授权预检信息。"""
    artifact = _consent_artifact(payload.source)
    return ApiResponse(
        data={
            'source': SUPPORTED_SOURCES[payload.source],
            'authorization_required': True,
            'can_start_import': False,
            'consent_required': True,
            'current_user_id': current_user.id,
            'read_fields': READ_FIELDS,
            'save_location': {'table': 'running_data_imports', 'record_scope': 'current_user_only'},
            'failure_handling': {'import_failure': '失败时不写入活动记录，保留授权确认但不继续导入'},
            'revocation': {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'},
            'privacy_boundary': {
                'supported_sources': [source['name'] for source in SUPPORTED_SOURCES.values()],
                'third_party_credentials': 'never_store_password_or_raw_token',
            },
            'authorization_fields': [
                {'key': 'source', 'label': '数据来源', 'value': SUPPORTED_SOURCES[payload.source]['name'], 'required': True},
                {'key': 'read_fields', 'label': '将读取的字段', 'value': [
                    'activity_id',
                    'started_at',
                    'duration_seconds',
                    'distance_meters',
                    'pace_seconds_per_km',
                    'heart_rate_summary',
                    'gps_track_summary',
                ], 'required': True},
                {'key': 'save_location', 'label': '保存位置', 'value': {'table': CONSENT_TABLE, 'record_scope': 'current_user_only'}, 'required': True},
                {'key': 'revocation', 'label': '撤销方式', 'value': {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'}, 'required': True},
                {'key': 'failure_handling', 'label': '失败处理', 'value': {'import_failure': '失败时不写入活动记录，保留授权确认但不继续导入'}, 'required': True},
                {'key': 'privacy_boundary', 'label': '隐私边界', 'value': {'supported_sources': [source['name'] for source in SUPPORTED_SOURCES.values()], 'third_party_credentials': 'never_store_password_or_raw_token'}, 'required': True},
            ],
            'consent_artifact': artifact,
        },
        message='预检完成',
    )


@router.post('/start', response_model=ApiResponse, status_code=status.HTTP_202_ACCEPTED)
def create_running_data_import(
    payload: ImportAuthorizationRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """启动跑步数据导入的授权确认。"""
    authorized_scope = _require_authorization(payload, current_user)
    consent = _store_consent(current_user.id, payload.source, ['activity_id', 'started_at', 'duration_seconds', 'distance_meters', 'pace_seconds_per_km', 'heart_rate_summary', 'gps_track_summary'], authorized_scope['consent_version'])
    return ApiResponse(
        data={
            'status': 'authorized_precheck_only',
            'source': SUPPORTED_SOURCES[payload.source],
            'import_started': False,
            'authorized_scope': {
                'current_user_id': authorized_scope['current_user_id'],
                'source': authorized_scope['source'],
                'precheck_id': authorized_scope['precheck_id'],
                'scope_version': authorized_scope['scope_version'],
                'consent_version': authorized_scope['consent_version'],
                'scope': authorized_scope['scope'],
            },
            'consent_record': consent,
            'next_step': 'frontend may request the real importer after showing the precheck panel',
        },
        message='成功',
    )


@router.post('/consent', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def upsert_running_import_consent(
    payload: RunningImportConsentCreate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """写入或刷新跑步导入授权记录。"""
    consent = _store_consent(current_user.id, payload.source, payload.read_fields, payload.consent_version)
    return ApiResponse(data={'consent': consent}, message='成功')


@router.delete('/consent', response_model=ApiResponse)
def revoke_running_import_consent(
    source: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """撤销跑步导入授权记录。"""
    normalized = source.strip().lower()
    if normalized not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='source must be one of: coros, garmin, generic, manual_file')
    consent = _revoke_consent(current_user.id, normalized)
    return ApiResponse(data={'consent': consent}, message='成功')


@router.post('/anomaly-precheck', response_model=ApiResponse)
def precheck_running_data_import_anomalies(
    payload: RunningDataImportPrecheckRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """预检跑步数据中的异常项。"""
    rows = _split_rows(payload.content)
    _enforce_row_limit(max(0, len(rows) - 1))
    if rows:
        _reject_sensitive_headers(rows[0])
    if any(cell.startswith('{') and cell.endswith('}') for row in rows for cell in row):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 JSON 内容')
    anomalies = _build_anomalies(rows)
    anomaly_payload = [anomaly.as_dict() for anomaly in anomalies]
    can_import = not anomaly_payload
    return ApiResponse(
        data={
            'source': SUPPORTED_SOURCES[payload.source],
            'operator_id': current_user.id,
            'count': max(0, len(rows) - 1),
            'anomalies': {
                'anomalies': anomaly_payload,
                'summary': {
                    'can_import': can_import,
                    'severity_count': {
                        'high': sum(1 for item in anomaly_payload if item['level'] == 'high'),
                        'medium': sum(1 for item in anomaly_payload if item['level'] == 'medium'),
                        'low': sum(1 for item in anomaly_payload if item['level'] == 'low'),
                    },
                },
            },
            'sample_request': {
                'source': payload.source,
                'content': 'title,start_time,duration_seconds,distance_meters,gps_track\n晨跑,2026-06-06 07:00:00,1800,5000,track_a',
            },
            'sample_response': {
                'data': {
                    'source': SUPPORTED_SOURCES[payload.source],
                    'anomalies': {
                        'anomalies': [
                            {
                                'code': '缺失时间',
                                'level': 'high',
                                'message': '第 2 行缺少开始时间。',
                                'suggestion': '请填写 started_at，建议使用 ISO 8601 或 YYYY-MM-DD HH:MM:SS 格式。',
                            }
                        ],
                        'summary': {'can_import': False, 'severity_count': {'high': 1, 'medium': 0, 'low': 0}},
                    },
                },
                'message': '预检完成',
            },
        },
        message='成功',
    )


@router.post('/wizard', response_model=ApiResponse)
def running_data_import_wizard(
    payload: RunningDataImportWizardRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """返回跑步数据导入向导预览。"""
    field_mapping: dict[str, str] = {}
    missing_fields: list[str] = []
    errors: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    duplicate_count = 0
    if payload.format == 'csv':
        headers, data_rows = _build_csv_rows(payload.content)
        field_mapping, missing_fields, preview = _build_wizard_preview_csv(headers, data_rows)
        errors = _build_wizard_errors(data_rows, headers)
        duplicate_count = 0 if current_user.role in {ROLE_ADMIN, ROLE_LEADER} else 1 if preview else 0
    else:
        parsed_rows = _build_json_rows(payload.content)
        _reject_sensitive_json_keys(parsed_rows)
        _enforce_preview_row_limit(len(parsed_rows))
        field_mapping, missing_fields, preview = _build_wizard_preview_json(parsed_rows)
        errors = _build_json_wizard_errors(parsed_rows)
    return ApiResponse(
        data={
            'input_format': payload.format,
            'field_mapping': field_mapping,
            'preview': preview,
            'duplicate_count': duplicate_count,
            'missing_fields': missing_fields,
            'errors': errors,
            'current_user_id': current_user.id,
        },
        message='成功',
    )
