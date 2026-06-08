"""Add list_activity_attendance to repository.py."""
PROJECT = __import__('pathlib').Path('/root/autodl-tmp/projects/hermes-swarm-lab')
path = PROJECT / 'backend' / 'repository.py'
content = path.read_text()

old = ('def reset_database() -> None:\n'
       '    """Reset database to clean state (for tests)."""\n'
       '    from .database import DB_PATH, init_db as _init_db\n'
       '    _init_db(DB_PATH)')

new = ('def reset_database() -> None:\n'
       '    """Reset database to clean state (for tests)."""\n'
       '    from .database import DB_PATH, init_db as _init_db\n'
       '    _init_db(DB_PATH)\n'
       '\n'
       '\n'
       'def list_activity_attendance(activity_id: int) -> list:\n'
       '    """List attendance records for an activity.\n'
       '\n'
       '    Args:\n'
       '        activity_id: Activity primary key.\n'
       '\n'
       '    Returns:\n'
       '        List of Attendance model instances.\n'
       '    """\n'
       '    from .attendance import list_attendance as _list\n'
       '    return _list(activity_id)')

if old in content:
    content = content.replace(old, new)
    path.write_text(content)
    print('[OK] repository.py: added list_activity_attendance')
else:
    print('[WARN] pattern not found')
