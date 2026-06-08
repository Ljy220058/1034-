from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path('/root/autodl-tmp/projects/hermes-swarm-lab').resolve()


def normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 原始工作区路径。

    Returns:
        规范化后的绝对路径。

    Raises:
        ValueError: 当路径为空或不在项目目录内时抛出。
    """
    normalized = Path(workspace_path).expanduser().resolve()
    if normalized != PROJECT_ROOT and PROJECT_ROOT not in normalized.parents:
        raise ValueError('workspace_path 不是项目目录')
    return str(normalized)
