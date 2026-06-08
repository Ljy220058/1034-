from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .db import initialize_database
from .models import ApiResponse
from .routes import register_routes
from .routes.activity_share_card import router as activity_share_card_router
from .settings import build_readiness_status, format_readiness_summary

app = FastAPI(title='1034 Running Club API')
app.state.started_at = os.times().elapsed
app.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')
register_routes(app)
app.include_router(activity_share_card_router)


@dataclass(frozen=True)
class IdeaCandidate:
    """创意候选。

    Attributes:
        title: 创意标题。
        executability: 可执行度评分。
        dependencies: 依赖项列表。
        priority: 推荐优先级。
    """

    title: str
    executability: int
    dependencies: list[str]
    priority: int

    def as_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            'title': self.title,
            'executability': self.executability,
            'dependencies': self.dependencies,
            'priority': self.priority,
        }


def _normalize_keywords(keywords: str) -> list[str]:
    """拆分并清理关键词。

    Args:
        keywords: 原始关键词文本。

    Returns:
        标准化后的关键词列表。
    """
    return [item for item in (part.strip() for part in keywords.split()) if item]


def _build_idea_pool(keywords: list[str]) -> list[IdeaCandidate]:
    """构建创意候选池。

    Args:
        keywords: 标准化关键词列表。

    Returns:
        创意候选列表。
    """
    joined = '、'.join(keywords)
    return [
        IdeaCandidate(
            title=f'基于“{joined}”的主题活动看板',
            executability=92,
            dependencies=['活动表', '成员表', '签到记录'],
            priority=1,
        ),
        IdeaCandidate(
            title=f'围绕“{joined}”的自动报名提醒',
            executability=86,
            dependencies=['活动报名接口', '通知渠道'],
            priority=2,
        ),
        IdeaCandidate(
            title=f'“{joined}”相关跑团数据洞察卡片',
            executability=78,
            dependencies=['活动统计视图', '排行榜接口'],
            priority=3,
        ),
    ]


def _score_ideas(items: list[IdeaCandidate]) -> list[dict[str, Any]]:
    """排序并序列化创意候选。

    Args:
        items: 创意候选列表。

    Returns:
        排序后的字典列表。
    """
    return [item.as_dict() for item in sorted(items, key=lambda item: (-item.executability, item.priority))]


def _detail_message(detail: Any) -> str:
    """Convert exception detail to a user-facing Chinese message.

    Args:
        detail: FastAPI exception detail payload.

    Returns:
        Chinese-readable detail message.
    """
    if isinstance(detail, str):
        return detail
    return '请求处理失败'


def _error_payload(status_code: int, message: str, *, details: Any, error_code: str) -> dict[str, Any]:
    """Build structured validation error payload.

    Args:
        status_code: HTTP status code.
        message: Human-readable error message.
        details: Validation detail list.
        error_code: Stable machine-readable code.

    Returns:
        Structured error payload.
    """
    return {'detail': message, 'error': {'status_code': status_code, 'error_code': error_code, 'details': details}}


def _validation_detail_message(exc: RequestValidationError) -> str:
    """将请求校验异常转换为中文结构化错误描述。

    Args:
        exc: FastAPI 请求校验异常。

    Returns:
        可返回给客户端的错误描述。
    """
    errors = exc.errors()
    if not errors:
        return '请求参数错误'
    first = errors[0]
    message = str(first.get('msg', '请求参数错误'))
    if 'Value error,' in message:
        return message.split('Value error,', 1)[1].strip()
    if message.startswith('Input should be'):
        return '输入校验失败'
    if first.get('type') == 'literal_error':
        return 'Input should be one of beginner, intermediate or advanced'
    return message


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={'detail': _validation_detail_message(exc)},
    )


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and 'error' in detail:
        payload = detail
    else:
        payload = {'detail': _detail_message(detail)}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': '服务器内部错误'},
    )


@app.get('/')
def root() -> dict[str, str]:
    return {'message': '1034 Running Club backend is running. Visit /docs for the API documentation.'}


@app.get('/healthz')
def healthz() -> dict[str, object]:
    return {
        'status': 'ok',
        'uptime': max(0.0, os.times().elapsed - app.state.started_at),
        'version': app.state.version,
    }


@app.get('/health')
def health_check() -> dict[str, object]:
    readiness = build_readiness_status()
    return {
        'status': 'ok' if readiness.ready else 'degraded',
        'ready': readiness.ready,
        'summary': format_readiness_summary(readiness),
        'workspace': {
            'project_root': str(readiness.project_root),
            'workspace_root': str(readiness.workspace_root),
            'stale_workspace_artifacts': list(readiness.stale_workspace_artifacts),
        },
        'readiness': {
            'required_env_vars': list(readiness.required_env_vars),
            'missing_env_vars': list(readiness.missing_env_vars),
            'database_path': str(readiness.database_path),
            'database_exists': readiness.database_exists,
            'stale_workspace_artifacts': list(readiness.stale_workspace_artifacts),
        },
    }


@app.get('/health/ready')
def readiness_check() -> dict[str, object]:
    readiness = build_readiness_status()
    return {
        'ready': readiness.ready,
        'missing_env_vars': list(readiness.missing_env_vars),
        'database_path': str(readiness.database_path),
        'workspace_root': str(readiness.workspace_root),
        'stale_workspace_artifacts': list(readiness.stale_workspace_artifacts),
        'summary': format_readiness_summary(readiness),
    }


@app.get('/health/sync')
def workspace_sync_healthcheck() -> dict[str, object]:
    readiness = build_readiness_status()
    return {
        'status': 'ok' if readiness.ready else 'degraded',
        'ready': readiness.ready,
        'summary': format_readiness_summary(readiness),
        'workspace': {
            'project_root': str(readiness.project_root),
            'workspace_root': str(readiness.workspace_root),
            'stale_workspace_artifacts': list(readiness.stale_workspace_artifacts),
        },
        'readiness': {
            'required_env_vars': list(readiness.required_env_vars),
            'missing_env_vars': list(readiness.missing_env_vars),
            'database_path': str(readiness.database_path),
            'database_exists': readiness.database_exists,
            'stale_workspace_artifacts': list(readiness.stale_workspace_artifacts),
        },
    }


@app.get('/api/v1/creative/recommendations')
def creative_recommendations(keywords: str = Query(..., min_length=1, description='主题关键词，空格分隔')) -> dict[str, object]:
    """根据主题关键词返回 3 条中文功能创意。

    Args:
        keywords: 主题关键词，多个词使用空格分隔。

    Returns:
        包含创意列表、可执行度、依赖和推荐优先级的响应。

    Raises:
        HTTPException: 当关键词为空时返回 422。
    """
    normalized = _normalize_keywords(keywords)
    if not normalized:
        raise HTTPException(status_code=422, detail='关键词不能为空')

    ideas = _score_ideas(_build_idea_pool(normalized))
    return {
        'data': {
            'keywords': normalized,
            'ideas': ideas,
        },
        'message': '已生成创意推荐',
    }


@app.get('/api/v1/creative/recommendations/sample')
def creative_recommendations_sample() -> dict[str, object]:
    """返回创意推荐接口示例。"""
    return creative_recommendations('跑团 训练 活动')


@app.on_event('startup')
def startup_event() -> None:
    """初始化应用依赖的数据库。"""
    initialize_database()
