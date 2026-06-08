from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path('/root/autodl-tmp/projects/hermes-swarm-lab').resolve()


def validate_workspace_access_path(workspace_path: str | Path | None) -> str:
    """Validate a workspace path for project-scoped operations.

    Args:
        workspace_path: Raw workspace path to validate.

    Returns:
        Normalized absolute workspace path.

    Raises:
        ValueError: If the workspace path is missing or outside the project root.
    """
    if workspace_path is None:
        raise ValueError('workspace_path 不是项目目录')

    candidate = Path(workspace_path).expanduser().resolve()
    if candidate != PROJECT_ROOT:
        raise ValueError('workspace_path 不是项目目录')
    return str(candidate)
