from __future__ import annotations

from backend.task_import import batch_import_task_metadata, normalize_task_import_status


def test_normalize_task_import_status_maps_doing_to_running() -> None:
    assert normalize_task_import_status('doing') == 'running'


def test_normalize_task_import_status_keeps_supported_statuses() -> None:
    assert normalize_task_import_status('todo') == 'todo'
    assert normalize_task_import_status('running') == 'running'
    assert normalize_task_import_status('done') == 'done'


def test_batch_import_task_metadata_accepts_doing_status() -> None:
    result = batch_import_task_metadata(
        [
            {
                'task_key': 'task-001',
                'title': '导入任务状态',
                'description': '验证 doing 会被统一为 running',
                'status': 'doing',
                'priority': 1,
            },
            {
                'task_key': 'task-002',
                'title': '保留原状态',
                'description': '验证 todo 仍然可用',
                'status': 'todo',
                'priority': 2,
            },
        ],
        workspace_path='/root/autodl-tmp/projects/hermes-swarm-lab',
    )

    assert result.count == 2
    assert result.items[0].status == 'running'
