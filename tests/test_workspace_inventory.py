from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.settings import assert_within_workspace, detect_workspace_bootstrap, workspace_bootstrap_report
from scripts.workspace_inventory import build_inventory

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_bootstrap_detects_current_project_workspace(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(ROOT))

    bootstrap = detect_workspace_bootstrap(ROOT)

    assert bootstrap.project_root == ROOT
    assert bootstrap.workspace_root == ROOT
    assert bootstrap.workspace_kind == 'project'
    assert bootstrap.workspace_exists is True
    assert bootstrap.workspace_matches_project is True
    assert bootstrap.valid is True
    assert bootstrap.invalid_reason is None


def test_workspace_bootstrap_rejects_missing_workspace(monkeypatch, tmp_path) -> None:
    missing_workspace = tmp_path / 'missing-workspace'
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(missing_workspace))

    bootstrap = detect_workspace_bootstrap(ROOT)

    assert bootstrap.workspace_root == missing_workspace.resolve()
    assert bootstrap.workspace_exists is False
    assert bootstrap.valid is False
    assert bootstrap.invalid_reason and 'workspace does not exist' in bootstrap.invalid_reason


def test_assert_within_workspace_rejects_outside_paths(tmp_path) -> None:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    inside = workspace / 'nested' / 'file.txt'
    inside.parent.mkdir(parents=True)
    inside.write_text('ok', encoding='utf-8')

    assert assert_within_workspace(inside, workspace) == inside.resolve()

    outside = tmp_path / 'outside.txt'
    outside.write_text('nope', encoding='utf-8')

    try:
        assert_within_workspace(outside, workspace)
    except Exception as exc:  # noqa: BLE001
        assert 'refusing to write outside workspace' in str(exc)
    else:
        raise AssertionError('expected workspace guard to reject path outside workspace')


def test_workspace_inventory_emits_deterministic_json(tmp_path) -> None:
    inventory = build_inventory(ROOT)

    assert inventory['workspace_root'] == str(ROOT)
    assert inventory['top_level_directories'] == sorted(inventory['top_level_directories'])
    assert 'backend' in inventory['top_level_directories']
    assert 'frontend' in inventory['top_level_directories']
    assert 'scripts' in inventory['top_level_directories']
    assert inventory['required_directories'] == ['backend', 'frontend', 'docs', 'tests', 'migrations']
    assert inventory['required_files'] == ['README.md', 'requirements.txt', 'pytest.ini']
    assert inventory['missing_directories'] == []
    assert inventory['missing_files'] == []
    assert inventory['workspace_exists'] is True
    assert 'runnable_entrypoints' in inventory
    assert any(entry['path'] == 'scripts/start.sh' for entry in inventory['runnable_entrypoints'])
    assert any(entry['path'] == 'backend/main.py' for entry in inventory['runnable_entrypoints'])


def test_workspace_inventory_script_cli_outputs_json() -> None:
    result = subprocess.run(
        ['python', 'scripts/workspace_inventory.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload['workspace_root'] == str(ROOT)
    assert isinstance(payload['git_status'], dict) or payload['git_status'] is None
    assert isinstance(payload['top_level_directories'], list)
    assert isinstance(payload['runnable_entrypoints'], list)


def test_workspace_bootstrap_report_serializes_expected_fields(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(ROOT))

    report = workspace_bootstrap_report(ROOT)

    assert report['workspace_root'] == str(ROOT)
    assert report['workspace_kind'] == 'project'
    assert report['workspace_exists'] is True
    assert report['valid'] is True
    assert report['invalid_reason'] is None
