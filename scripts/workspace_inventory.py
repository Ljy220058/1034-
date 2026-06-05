from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRECTORIES = ('backend', 'frontend', 'docs', 'tests', 'migrations')
REQUIRED_FILES = ('README.md', 'requirements.txt', 'pytest.ini')


def _run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        'command': command,
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def _top_level_directories(root: Path) -> list[str]:
    dirs = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_dir() and entry.name != '.git':
            dirs.append(entry.name)
    return dirs


def _git_status(root: Path) -> dict[str, Any] | None:
    git_dir = root / '.git'
    if not git_dir.exists():
        return None
    result = _run(['git', 'status', '--short', '--branch'], cwd=root)
    if result['returncode'] != 0:
        return {
            'available': True,
            'error': result['stderr'].strip() or result['stdout'].strip(),
        }
    lines = [line.rstrip() for line in result['stdout'].splitlines() if line.strip()]
    return {
        'available': True,
        'branch_summary': lines[0] if lines else '',
        'changes': lines[1:] if len(lines) > 1 else [],
    }


def _is_runnable_entrypoint(path: Path) -> bool:
    try:
        first_lines = path.read_text(encoding='utf-8').splitlines()[:12]
    except Exception:
        return False
    text = '\n'.join(first_lines)
    if path.name == 'main.py' and 'from .app import app' in text:
        return True
    return (
        path.name.endswith('.sh')
        or 'if __name__ == "__main__"' in text
        or 'if __name__ == \"__main__\"' in text
        or 'uvicorn ' in text
        or 'fastapi' in text.lower() and 'app =' in text
    )


def _entrypoint_kind(path: Path) -> str:
    if path.suffix in {'.sh', '.bash'}:
        return 'shell'
    if path.suffix == '.py':
        return 'python'
    return 'unknown'


def _discover_entrypoints(root: Path) -> list[dict[str, str]]:
    candidates: list[Path] = []
    for rel in [
        'scripts',
        'backend',
        'frontend',
        'deploy',
        'docs',
        'migrations',
        '.',
    ]:
        base = root / rel if rel != '.' else root
        if not base.exists():
            continue
        for path in sorted(base.rglob('*')):
            if not path.is_file():
                continue
            if path.suffix not in {'.py', '.sh', '.bash'}:
                continue
            if _is_runnable_entrypoint(path):
                candidates.append(path)
    seen = set()
    entries = []
    for path in sorted(candidates):
        rel = str(path.relative_to(root))
        if rel in seen:
            continue
        seen.add(rel)
        entries.append({
            'path': rel,
            'kind': _entrypoint_kind(path),
        })
    return entries


def _missing_directories(root: Path) -> list[str]:
    return [name for name in REQUIRED_DIRECTORIES if not (root / name).is_dir()]


def _missing_files(root: Path) -> list[str]:
    return [name for name in REQUIRED_FILES if not (root / name).is_file()]


def build_inventory(root: Path = ROOT) -> dict[str, Any]:
    return {
        'workspace_root': str(root),
        'top_level_directories': _top_level_directories(root),
        'required_directories': list(REQUIRED_DIRECTORIES),
        'required_files': list(REQUIRED_FILES),
        'missing_directories': _missing_directories(root),
        'missing_files': _missing_files(root),
        'workspace_exists': root.exists(),
        'git_status': _git_status(root),
        'runnable_entrypoints': _discover_entrypoints(root),
    }


def main(argv: list[str] | None = None) -> int:
    payload = build_inventory(ROOT)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
