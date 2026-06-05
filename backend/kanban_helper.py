from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

DEFAULT_WORKSPACE: Final[str] = '/root/autodl-tmp/projects/hermes-swarm-lab'


@dataclass(frozen=True)
class KanbanTaskSpec:
    title: str
    body: str
    assignee: str
    workspace: str = DEFAULT_WORKSPACE

    def as_kanban_args(self) -> dict[str, object]:
        workspace_path = Path(self.workspace)
        if not workspace_path.is_absolute():
            raise ValueError(f'workspace must be absolute: {self.workspace}')
        return {
            'title': self.title,
            'body': self.body,
            'assignee': self.assignee,
            'workspace_kind': 'dir',
            'workspace_path': str(workspace_path),
        }


def build_workspace_scoped_tasks() -> list[KanbanTaskSpec]:
    workspace_note = f'dir:{DEFAULT_WORKSPACE}'
    return [
        KanbanTaskSpec(
            title='Backend: add workspace-scoped kanban task creation endpoint',
            assignee='backend-dev',
            body=(
                'Implement a small FastAPI helper or CLI entrypoint that creates a workspace-scoped '
                'Kanban task using the shared repository workspace. The task must be executable, '
                'ready for idle backend work, and always resolve the workspace to '
                f'{workspace_note}. Acceptance criteria: inputs validated, task payload persisted, '
                'and the resulting task data is returned for orchestration.'
            ),
        ),
        KanbanTaskSpec(
            title='Backend: add regression tests for workspace-scoped kanban task creation',
            assignee='backend-dev',
            body=(
                'Add tests covering the workspace-scoped Kanban task creation helper or CLI path. '
                'Verify exactly two tasks are created for the orchestration flow, the workspace '
                f'is passed through as {workspace_note}, and the helper rejects malformed workspace '
                'values. Acceptance criteria: tests exercise the creation flow end-to-end and protect '
                'the workspace contract.'
            ),
        ),
    ]


def create_task_payloads() -> list[dict[str, object]]:
    return [task.as_kanban_args() for task in build_workspace_scoped_tasks()]
