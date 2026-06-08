from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "blocked_task_advice_cli.py"


def run_advice(snapshot: list[dict]) -> str:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--from-json", "-"],
        input=json.dumps(snapshot, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_no_blocked_tasks_outputs_clear_chinese_message():
    output = run_advice([
        {"id": "t_run", "title": "正常运行", "status": "running", "assignee": "worker-a"},
        {"id": "t_sched", "title": "定时巡检", "status": "scheduled", "assignee": "worker-b"},
    ])

    assert "当前没有需要解除阻塞的任务" in output
    assert "t_run" not in output
    assert "t_sched" not in output


def test_single_blocked_task_outputs_copyable_advice_for_common_reason():
    output = run_advice([
        {
            "id": "t_blocked",
            "title": "等待测试结果",
            "status": "blocked",
            "assignee": "qa-worker",
            "workspace_path": "/tmp/workspace-a",
            "block_reason": "缺少测试结果，无法判断是否通过。",
        }
    ])

    assert "【任务 t_blocked】等待测试结果" in output
    assert "可复制到看板评论" in output
    assert "缺少测试结果" in output
    assert "请先运行最小相关测试" in output
    assert "qa-worker" in output


def test_multiple_blocked_tasks_include_dependency_contract_and_workspace_advice_only():
    output = run_advice([
        {"id": "t_running", "title": "正在处理", "status": "running", "assignee": "worker"},
        {
            "id": "t_contract",
            "title": "接口联调",
            "status": "blocked",
            "assignee": "backend-dev",
            "block_reason": "接口契约不清，字段含义待确认。",
        },
        {
            "id": "t_dep",
            "title": "依赖任务未完成",
            "status": "blocked",
            "assignee": "frontend-dev",
            "block_reason": "依赖任务 t_parent 未完成。",
        },
        {
            "id": "t_workspace",
            "title": "工作区异常",
            "status": "blocked",
            "assignee": "ops-worker",
            "workspace_path": "/missing/workspace",
            "block_reason": "工作区路径异常，无法进入目录。",
        },
    ])

    assert "【任务 t_contract】接口联调" in output
    assert "请把当前理解的请求/响应字段" in output
    assert "【任务 t_dep】依赖任务未完成" in output
    assert "先检查父任务/依赖任务状态" in output
    assert "【任务 t_workspace】工作区异常" in output
    assert "请先验证工作区路径是否存在且可写" in output
    assert "t_running" not in output
