from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(os.getenv('RUNNING_CLUB_DB_PATH') or (Path(tempfile.gettempdir()) / 'running_club.db'))
REQUIRED_ENV_VARS = ('RUNNING_CLUB_DB_PATH',)
EXPECTED_WORKSPACE_ENTRIES = {
    'README.md',
    'backend',
    'frontend',
    'docs',
    'tests',
    'migrations',
    'requirements.txt',
    'pytest.ini',
}


@dataclass(frozen=True)
class WorkspaceBootstrap:
    requested_workspace: Path | None
    project_root: Path
    workspace_root: Path
    workspace_kind: str
    workspace_exists: bool
    workspace_matches_project: bool
    invalid_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'requested_workspace': str(self.requested_workspace) if self.requested_workspace else None,
            'project_root': str(self.project_root),
            'workspace_root': str(self.workspace_root),
            'workspace_kind': self.workspace_kind,
            'workspace_exists': self.workspace_exists,
            'workspace_matches_project': self.workspace_matches_project,
            'invalid_reason': self.invalid_reason,
            'valid': self.valid,
        }

    @property
    def valid(self) -> bool:
        return self.invalid_reason is None


@dataclass(frozen=True)
class Settings:
    project_root: Path
    workspace_root: Path | None = None
    database_path: Path = DEFAULT_DB_PATH
    workspace_bootstrap: WorkspaceBootstrap | None = None


@dataclass(frozen=True)
class ReadinessStatus:
    required_env_vars: tuple[str, ...]
    missing_env_vars: tuple[str, ...]
    database_path: Path
    database_exists: bool
    project_root: Path
    workspace_root: Path
    stale_workspace_artifacts: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_env_vars and self.database_exists and not self.stale_workspace_artifacts


class WorkspaceBootstrapError(RuntimeError):
    pass


def _resolve_workspace_kind(workspace_root: Path, project_root: Path) -> str:
    if workspace_root == project_root:
        return 'project'
    if workspace_root.name.startswith('wt-') or workspace_root.parent.name == 'worktrees':
        return 'worktree'
    if workspace_root == Path('/'):
        return 'root'
    return 'dir'


def detect_workspace_bootstrap(project_root: Path | None = None) -> WorkspaceBootstrap:
    root = Path(project_root or Path.cwd()).resolve()
    requested_raw = os.getenv('HERMES_KANBAN_WORKSPACE')
    requested = Path(requested_raw).expanduser().resolve() if requested_raw else None
    workspace_root = requested or root
    workspace_kind = _resolve_workspace_kind(workspace_root, root)
    workspace_exists = workspace_root.exists()
    workspace_matches_project = workspace_root == root
    invalid_reason = None
    if requested_raw is None:
        invalid_reason = 'HERMES_KANBAN_WORKSPACE is not set'
    elif not workspace_exists:
        invalid_reason = f'workspace does not exist: {workspace_root}'
    elif not workspace_matches_project and not root.is_relative_to(workspace_root):
        invalid_reason = f'project root {root} is outside workspace {workspace_root}'
    return WorkspaceBootstrap(
        requested_workspace=requested,
        project_root=root,
        workspace_root=workspace_root,
        workspace_kind=workspace_kind,
        workspace_exists=workspace_exists,
        workspace_matches_project=workspace_matches_project,
        invalid_reason=invalid_reason,
    )


def assert_within_workspace(path: Path, workspace_root: Path | None = None) -> Path:
    workspace = Path(workspace_root or detect_workspace_bootstrap().workspace_root).resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError:
        if workspace_root is None and candidate.exists():
            return candidate
        raise WorkspaceBootstrapError(f'refusing to write outside workspace: {candidate} (workspace: {workspace})')
    return candidate


def workspace_bootstrap_report(project_root: Path | None = None) -> dict[str, Any]:
    bootstrap = detect_workspace_bootstrap(project_root)
    return bootstrap.as_dict()


def get_settings() -> Settings:
    database_path = Path(os.getenv('RUNNING_CLUB_DB_PATH') or DEFAULT_DB_PATH)
    root = Path.cwd()
    bootstrap = detect_workspace_bootstrap(root)
    return Settings(project_root=root, workspace_root=bootstrap.workspace_root, database_path=database_path, workspace_bootstrap=bootstrap)


def _detect_workspace_root(project_root: Path) -> Path:
    candidate = project_root
    nested = project_root / 'tmp' / 'repo' / 'main' / 'xianyu1102' / 'hermes-swarm-lab'
    if nested.exists():
        candidate = nested
    elif project_root.name != 'hermes-swarm-lab' and (project_root / 'README.md').exists():
        candidate = project_root
    return candidate


def _stale_workspace_artifacts(workspace_root: Path) -> tuple[str, ...]:
    if not workspace_root.exists():
        return ('workspace-root-missing',)
    missing = sorted(name for name in EXPECTED_WORKSPACE_ENTRIES if not (workspace_root / name).exists())
    return tuple(f'missing:{name}' for name in missing)


def build_readiness_status(project_root: Path | None = None, database_path: Path | None = None) -> ReadinessStatus:
    root = Path(project_root or Path.cwd()).resolve()
    workspace_root = _detect_workspace_root(root)
    db_path = Path(database_path or os.getenv('RUNNING_CLUB_DB_PATH') or DEFAULT_DB_PATH)
    missing = tuple(name for name in REQUIRED_ENV_VARS if not os.getenv(name))
    return ReadinessStatus(
        required_env_vars=REQUIRED_ENV_VARS,
        missing_env_vars=missing,
        database_path=db_path,
        database_exists=db_path.exists(),
        project_root=root,
        workspace_root=workspace_root,
        stale_workspace_artifacts=_stale_workspace_artifacts(workspace_root),
    )


def format_readiness_summary(status: ReadinessStatus) -> str:
    if status.ready:
        env_summary = 'all required env vars set'
        db_summary = f'database found at {status.database_path}'
        workspace_summary = f'workspace clean at {status.workspace_root}'
        overall = 'READY'
    else:
        env_summary = 'missing env vars: ' + ', '.join(status.missing_env_vars) if status.missing_env_vars else 'all required env vars set'
        db_summary = f'database missing at {status.database_path}' if not status.database_exists else f'database found at {status.database_path}'
        workspace_summary = 'stale workspace artifacts: ' + ', '.join(status.stale_workspace_artifacts) if status.stale_workspace_artifacts else f'workspace clean at {status.workspace_root}'
        overall = 'NOT READY'
    return f'{overall} | env: {env_summary} | db: {db_summary} | workspace: {workspace_summary} | root: {status.project_root}'
