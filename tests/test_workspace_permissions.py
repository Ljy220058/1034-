from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.routes.common import CurrentUser, get_current_user


class DummyMember:
    """测试用成员对象。"""

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """序列化成员。

        Args:
            mode: 序列化模式。

        Returns:
            成员字典。
        """
        return {'id': 99, 'role': 'member'}


def _user(role: str) -> CurrentUser:
    """构造测试当前用户。

    Args:
        role: 用户角色。

    Returns:
        当前用户对象。
    """
    return CurrentUser(id=99, role=role, member=DummyMember())


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    """每个用例后清理 FastAPI 依赖覆盖。

    Yields:
        None。
    """
    yield
    app.dependency_overrides.clear()


def _client_for_role(role: str) -> TestClient:
    """创建指定角色的测试客户端。

    Args:
        role: 用户角色。

    Returns:
        TestClient 实例。
    """
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    'path',
    [
        '/api/v1/workspaces/tasks',
        '/api/v1/workspaces/tasks/items',
        '/api/v1/workers/board',
        '/api/v1/workers/summary',
        '/api/v1/workers/recommendations',
    ],
)
def test_workspace_worker_panel_endpoints_reject_member(path: str) -> None:
    """普通成员不能读取工作区任务和 worker 面板接口。

    Args:
        path: 接口路径。
    """
    client = _client_for_role('member')
    response = client.get(path, params={'workspace_path': str(Path.cwd())})

    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}


def test_workspace_tasks_rejects_untrusted_workspace_path_for_leader(tmp_path: Path) -> None:
    """团长不能通过 workspace_path 读取受信工作区之外的路径。

    Args:
        tmp_path: pytest 临时目录。
    """
    client = _client_for_role('leader')
    response = client.get('/api/v1/workspaces/tasks', params={'workspace_path': str(tmp_path)})

    assert response.status_code == 422
    assert response.json() == {'detail': '工作区路径不受信任'}
