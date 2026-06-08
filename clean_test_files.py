"""Clean line number prefixes from corrupted test files and restore from git."""
import subprocess, sys
from pathlib import Path

PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Strategy 1: Use git to restore files (cleanest)
# Strategy 2: Clean line number prefixes from Python files
# Strategy 3: Use git show to get original content

test_files = [
    'tests/test_api.py',
    'tests/test_auth.py',
    'tests/test_checkin.py',
    'tests/test_kanban_helper.py',
    'tests/test_main.py',
    'tests/test_task_discovery.py',
    'tests/test_task_queue_worker_intake.py',
    'tests/test_workspace_inventory.py',
    'tests/frontend.test.js',
]

for tf in test_files:
    path = PROJECT / tf
    if not path.exists():
        print(f'{tf}: does not exist, skipping')
        continue

    # Check if file has line number corruption
    first_line = path.read_text().split('\n')[0]
    if '|' in first_line and first_line.strip().startswith(('1|', '1 |')):
        print(f'{tf}: CORRUPTED with line numbers')

        # Try to get clean version from git
        result = subprocess.run(
            ['git', 'show', f'HEAD:{tf}'],
            cwd=PROJECT,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            path.write_text(result.stdout)
            print(f'  -> Restored from git HEAD')
        else:
            # Clean line numbers manually
            import re
            content = path.read_text()
            # Pattern: "   N|     N|content" or "N|N|content"
            cleaned = re.sub(r'^\s*\d+\|\s*\d+\|', '', content, flags=re.MULTILINE)
            path.write_text(cleaned)
            print(f'  -> Cleaned line numbers manually')
    else:
        print(f'{tf}: OK (no corruption)')
