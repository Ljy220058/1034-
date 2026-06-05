from __future__ import annotations

import os
from functools import wraps
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .db import initialize_database
from .settings import build_readiness_status, format_readiness_summary

app = FastAPI(title='1034 Running Club API')
import time

app.state.started_at = time.monotonic()
app.state.version = os.getenv('RUNNING_CLUB_VERSION', '0.1.0')


def _error_payload(code: int, message: str, *, details: object | None = None, error_code: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        'error': {
            'code': error_code or f'http_{code}',
            'message': message,
        }
    }
    if details is not None:
        payload['error']['details'] = details
    return payload


def _legacy_detail_payload(detail: object) -> dict[str, object]:
    return {'detail': detail}


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={'detail': exc.errors(), **_error_payload(422, 'Request validation failed', details=exc.errors(), error_code='validation_error')},
    )


def _detail_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        error = detail.get('error')
        if isinstance(error, dict) and isinstance(error.get('message'), str):
            return error['message']
    return 'request failed'


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and 'error' in detail:
        payload = detail
    else:
        payload = _legacy_detail_payload(_detail_message(detail))
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(500, 'An unexpected error occurred'),
    )


@app.get('/')
def root() -> dict[str, str]:
    return {'message': '1034 Running Club backend is running. Visit /docs for the API documentation.'}


@app.get('/healthz')
def healthz() -> dict[str, object]:
    return {
        'status': 'ok',
        'uptime': max(0.0, time.monotonic() - app.state.started_at),
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
        },
    }


@app.on_event('startup')
def startup_event() -> None:
    initialize_database()
