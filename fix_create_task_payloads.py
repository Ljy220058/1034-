"""Add missing create_task_payloads to task_discovery.py."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

td_path = PROJECT / 'backend' / 'task_discovery.py'
td = td_path.read_text()

fn = '''

def create_task_payloads() -> list[dict]:
    """Create default kanban task payloads for creative task flows.

    Returns:
        List of task payload dicts.
    """
    return [
        {
            'task_key': 'creative-task-001',
            'title': '生成活动创意',
            'status': 'todo',
            'description': '自动生成社群活动创意任务',
            'assignee': None,
            'priority': 5,
        },
        {
            'task_key': 'creative-task-002',
            'title': '审核活动方案',
            'status': 'todo',
            'description': '审核并优化自动生成的活动方案',
            'assignee': None,
            'priority': 4,
        },
    ]

'''

# Insert before list_workspace_tasks or at end
marker = '\n\ndef list_workspace_tasks'
if marker in td:
    td = td.replace(marker, fn + marker, 1)
    td_path.write_text(td)
    print('[OK] task_discovery.py: added create_task_payloads')
else:
    td = td.rstrip() + fn + '\n'
    td_path.write_text(td)
    print('[OK] task_discovery.py: appended create_task_payloads')
