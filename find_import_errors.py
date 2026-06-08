"""Find all broken imports in the Hermes project."""
import sys
sys.path.insert(0, '.')

modules = [
    'backend.models',
    'backend.database',
    'backend.db',
    'backend.attendance',
    'backend.task_board_models',
    'backend.worker_board',
    'backend.worker_recommendations',
    'backend.task_diagnostics',
    'backend.task_discovery',
    'backend.repository',
    'backend.settings',
    'backend.routes.common',
    'backend.routes.auth',
    'backend.routes.workers',
    'backend.routes.tasks',
    'backend.routes.task_imports',
    'backend.routes.workspaces',
    'backend.routes.checkins',
    'backend.routes.members',
    'backend.routes.activities',
    'backend.routes.announcements',
    'backend.routes.__init__',
    'backend.__init__',
    'backend.app',
]

for mod in modules:
    try:
        __import__(mod)
        print(f'  OK: {mod}')
    except Exception as e:
        print(f'FAIL: {mod} - {type(e).__name__}: {e}')
        break

print('Done')
