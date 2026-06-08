from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = '/root/autodl-tmp/projects/hermes-swarm-lab'


def _load_kanban_helper():
    spec = importlib.util.spec_from_file_location('kanban_helper_under_test', ROOT / 'backend' / 'kanban_helper.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None, '无法加载 kanban_helper.py'
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kanban_helper = _load_kanban_helper()
KanbanTaskSpec = kanban_helper.KanbanTaskSpec
create_task_payloads = kanban_helper.create_task_payloads


def _中文创意任务负载() -> list[dict[str, object]]:
    return create_task_payloads()


def _断言是中文任务(payload: dict[str, object]) -> None:
    assert any('\u4e00' <= char <= '\u9fff' for char in str(payload['title'])), '标题必须包含中文'
    assert any('\u4e00' <= char <= '\u9fff' for char in str(payload['body'])), '描述必须包含中文'


def test_创意任务创建_正常输入_生成正好两个任务负载():
    """创意任务创建流程必须稳定生成正好 2 个任务。"""
    # Arrange
    payloads = _中文创意任务负载()
    # Act
    count = len(payloads)
    # Assert
    assert count == 2, f'期望正好生成 2 个任务，实际生成 {count} 个'


def test_创意任务创建_正常输入_写入指定目录工作区():
    """每个创意任务都必须写入 dir 类型的指定项目工作区。"""
    # Arrange
    payloads = _中文创意任务负载()
    # Act
    workspaces = {(task['workspace_kind'], task['workspace_path']) for task in payloads}
    # Assert
    assert workspaces == {('dir', WORKSPACE)}, f'工作区必须为 dir:{WORKSPACE}'


def test_创意任务创建_正常输入_写入中文标题和中文描述():
    """每个创意任务必须包含中文标题和中文描述，便于中文看板阅读。"""
    # Arrange
    payloads = _中文创意任务负载()
    # Act
    invalid = [task for task in payloads if not all(key in task for key in ('title', 'body'))]
    # Assert
    assert invalid == [], '任务负载必须同时包含 title 和 body'
    for task in payloads:
        _断言是中文任务(task)


def test_创意任务创建_正常输入_写入负责人字段():
    """每个创意任务都必须写入非空负责人字段。"""
    # Arrange
    payloads = _中文创意任务负载()
    # Act
    assignees = [task.get('assignee') for task in payloads]
    # Assert
    assert all(isinstance(item, str) and item.strip() for item in assignees), '负责人不能为空'


def test_创意任务创建_重复调用_任务负载保持幂等不重复():
    """重复生成创意任务时必须保持相同任务集合，避免重复创建额外任务。"""
    # Arrange
    first = _中文创意任务负载()
    # Act
    second = _中文创意任务负载()
    # Assert
    assert second == first
    assert len({task['title'] for task in second}) == 2, '重复调用不得产生重复标题'


def test_创意任务创建_空白负责人_返回清晰中文错误():
    """空白负责人会导致看板任务无人处理，必须拒绝。"""
    # Arrange
    spec = KanbanTaskSpec(title='创意任务', body='创建中文创意任务', assignee='  \t  ')
    # Act
    with pytest.raises(ValueError, match='负责人不能为空'):
        spec.as_kanban_args()
    # Assert


def test_创意任务创建_相对工作区_返回清晰错误():
    """相对工作区路径会破坏 dir 工作区契约，必须拒绝。"""
    # Arrange
    spec = KanbanTaskSpec(title='创意任务', body='创建中文创意任务', assignee='writer', workspace='relative/path')
    # Act
    with pytest.raises(ValueError, match='workspace must be absolute'):
        spec.as_kanban_args()
    # Assert


def test_创意任务创建_工作区路径_保持绝对路径不被改写():
    """指定绝对工作区路径时，负载必须原样保留该目录。"""
    # Arrange
    spec = KanbanTaskSpec(title='创意任务', body='创建中文创意任务', assignee='writer', workspace=WORKSPACE)
    # Act
    payload = spec.as_kanban_args()
    # Assert
    assert payload['workspace_path'] == str(Path(WORKSPACE))
    assert payload['workspace_kind'] == 'dir'
