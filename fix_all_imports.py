"""Find and fix all broken imports in the Hermes project."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Approach: try importing the full package, fix errors one by one
import subprocess, sys

max_iterations = 20
for i in range(max_iterations):
    result = subprocess.run(
        [sys.executable, '-c', 'from backend.app import app'],
        cwd=PROJECT,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f'Iteration {i}: App imports OK!')
        break

    error = result.stderr.strip().split('\n')[-5:]
    error_text = '\n'.join(error)
    print(f'Iteration {i}: {error_text[:200]}')

    # Parse the error to find what's missing
    if 'cannot import name' in error_text:
        # Extract: cannot import name 'X' from 'backend.Y'
        for line in error.split('\n'):
            if 'cannot import name' in line:
                parts = line.split("'")
                if len(parts) >= 4:
                    name = parts[1]
                    module = parts[3]
                    print(f'  Missing: {name} from {module}')

                    # Fix specific known missing items
                    module_path = module.replace('.', '/')
                    py_file = PROJECT / f'{module_path}.py'

                    if name == 'build_task_health_summary' and module == 'backend.worker_board':
                        # Add the function to worker_board.py
                        code_to_add = '''
def build_task_health_summary(workspace_path: str | Path) -> dict[str, Any]:
    """Return task health counts grouped by health level.

    Args:
        workspace_path: Workspace directory path.

    Returns:
        Dict with workspace and health counts.
    """
    normalized = _normalize_workspace_path(workspace_path)
    items = list_workspace_task_health(workspace_path=normalized)
    counts = {'healthy': 0, 'at_risk': 0, 'blocked': 0, 'failing': 0}
    for item in items:
        level = item.get('health_level', 'healthy')
        if level in counts:
            counts[level] += 1
    return {
        'workspace_path': normalized,
        'total': len(items),
        'health_counts': counts,
    }
'''
                        content = py_file.read_text()
                        # Add before the last function or at end
                        marker = 'def build_worker_board_snapshot'
                        if marker in content:
                            content = content.replace(marker, code_to_add + '\n' + marker)
                            py_file.write_text(content)
                            print(f'  [FIXED] Added build_task_health_summary to worker_board.py')
                        else:
                            print(f'  [WARN] Could not find insertion point in worker_board.py')

                    elif name == 'WorkspaceBootstrapError':
                        # This should be in settings.py
                        settings_path = PROJECT / 'backend' / 'settings.py'
                        content = settings_path.read_text()
                        if 'class WorkspaceBootstrapError' not in content:
                            code = '\n\nclass WorkspaceBootstrapError(Exception):\n    """Raised when a workspace path fails validation."""\n    pass\n'
                            # Add before the first class
                            content = content.replace('class Settings:', code + '\nclass Settings:')
                            settings_path.write_text(content)
                            print(f'  [FIXED] Added WorkspaceBootstrapError to settings.py')

                    else:
                        print(f'  [UNKNOWN] No fix handler for {name}')

    elif 'No module named' in error_text:
        print(f'  Missing module (not fixable automatically)')
    elif 'SyntaxError' in error_text:
        print(f'  Syntax error (needs manual fix)')
    else:
        print(f'  Unrecognized error pattern')
else:
    print(f'FAILED: Could not fix imports after {max_iterations} iterations')
