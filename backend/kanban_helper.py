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
        """转换为 kanban_create 可使用的任务参数。

        Returns:
            包含标题、描述、负责人和目录工作区信息的任务参数。

        Raises:
            ValueError: 负责人为空或工作区不是绝对路径时抛出。
        """
        if not self.assignee.strip():
            raise ValueError('负责人不能为空')
        workspace_path = Path(self.workspace)
        if not workspace_path.is_absolute():
            raise ValueError(f'workspace must be absolute: {self.workspace}')
        return {
            'title': self.title,
            'body': self.body,
            'assignee': self.assignee.strip(),
            'workspace_kind': 'dir',
            'workspace_path': str(workspace_path),
        }


def build_workspace_scoped_tasks() -> list[KanbanTaskSpec]:
    """构建共享工作区范围内的创意后端任务。

    Returns:
        正好两个包含中文标题和中文描述的任务规格。
    """
    workspace_note = f'dir:{DEFAULT_WORKSPACE}'
    return [
        KanbanTaskSpec(
            title='后端：新增工作区范围的看板任务创建端点',
            assignee='backend-dev',
            body=(
                '实现一个小型 FastAPI 辅助模块或命令入口，用于在共享仓库工作区创建看板任务。'
                '任务必须可执行、适合空闲后端工作调度，并始终将工作区解析为 '
                f'{workspace_note}。验收标准：校验输入、持久化任务负载，并返回可供编排使用的任务数据。'
            ),
        ),
        KanbanTaskSpec(
            title='后端：补充工作区范围看板任务创建回归测试',
            assignee='backend-dev',
            body=(
                '补充覆盖工作区范围看板任务创建辅助模块或命令路径的测试。'
                '验证编排流程正好创建两个任务，工作区以 '
                f'{workspace_note} 传递，并且辅助模块会拒绝格式错误的工作区。'
                '验收标准：测试端到端覆盖创建流程，并保护工作区契约不被破坏。'
            ),
        ),
    ]


def create_task_payloads() -> list[dict[str, object]]:
    """生成创意任务创建流程使用的看板任务负载。

    Returns:
        可直接传给 kanban_create 的任务负载列表。
    """
    return [task.as_kanban_args() for task in build_workspace_scoped_tasks()]
