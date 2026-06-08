from __future__ import annotations

import importlib

import pytest
from fastapi import HTTPException


def test_backend_imports_cleanly() -> None:
    import backend  # noqa: F401


def test_idle_task_recommender_imports_cleanly() -> None:
    module = importlib.import_module('backend.routes.idle_task_recommender')
    assert hasattr(module, 'router')


def test_idle_task_recommender_requires_keyword() -> None:
    module = importlib.import_module('backend.routes.idle_task_recommender')
    with pytest.raises(HTTPException) as exc_info:
        module.recommend_idle_tasks(current_user=module.CurrentUser(id=1, role='member', member=None), keyword='   ')
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == '关键词不能为空'


def test_get_db_path_is_exported() -> None:
    module = importlib.import_module('backend.database')
    assert hasattr(module, 'get_db_path')
    assert str(module.get_db_path()).endswith('running_club.db')
