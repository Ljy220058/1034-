"""Apply the 4 key fixes needed for tests to pass."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Fix 1: models.py - AttendanceCreate.activity_id optional
mp = PROJECT / 'backend' / 'models.py'
mc = mp.read_text()
old1 = '    activity_id: int = Field(..., gt=0)'
new1 = '    activity_id: int | None = Field(default=None, gt=0)'
if old1 in mc:
    mc = mc.replace(old1, new1)
    mp.write_text(mc)
    print('[OK] models.py: AttendanceCreate.activity_id optional')
else:
    print('[WARN] models.py: pattern 1 not found')

# Fix 2: models.py - add field_validator import
old2 = 'from pydantic import BaseModel, Field'
new2 = 'from pydantic import BaseModel, Field, field_validator'
if old2 in mc:
    mc = mc.replace(old2, new2)
    mp.write_text(mc)
    print('[OK] models.py: field_validator import added')
elif 'field_validator' in mc.split('from pydantic import')[1].split('\n')[0] if 'from pydantic import' in mc else False:
    print('[OK] models.py: field_validator already imported')

# Fix 3: common.py - bootstrap logic
cp = PROJECT / 'backend' / 'routes' / 'common.py'
cc = cp.read_text()
old3 = "    if payload.__class__.__name__ == 'UserRegister' and data.get('role') != ROLE_MEMBER:\n        data['role'] = ROLE_MEMBER"
new3 = "    if payload.__class__.__name__ == 'UserRegister' and data.get('role') != ROLE_MEMBER:\n        # bootstrap: first user can be any role\n        from ..database import connect as _bc\n        with _bc() as _bconn:\n            _bcnt = _bconn.execute('SELECT COUNT(*) FROM members').fetchone()[0]\n        if _bcnt > 0:\n            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')"
if old3 in cc:
    cc = cc.replace(old3, new3)
    cp.write_text(cc)
    print('[OK] common.py: bootstrap logic added')
else:
    print('[WARN] common.py: pattern 3 not found')

# Fix 4: auth.py - remove hardcoded non-member rejection
ap = PROJECT / 'backend' / 'routes' / 'auth.py'
ac = ap.read_text()
old4 = "    sanitized_payload = sanitize_member_payload(payload)\n    if sanitized_payload.get('role') != 'member':\n        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')\n    member, outcome = create_member_with_password(sanitized_payload, password_hash)"
new4 = "    sanitized_payload = sanitize_member_payload(payload)\n    member, outcome = create_member_with_password(sanitized_payload, password_hash)"
if old4 in ac:
    ac = ac.replace(old4, new4)
    ap.write_text(ac)
    print('[OK] auth.py: removed redundant role check')
else:
    print('[WARN] auth.py: pattern 4 not found')

# Fix 5: db.py - task_id/parent_task_id in workspace_tasks
dp = PROJECT / 'backend' / 'db.py'
dc = dp.read_text()
old5 = "                metadata TEXT NOT NULL DEFAULT '{}',\n                UNIQUE(workspace, task_key)"
new5 = "                metadata TEXT NOT NULL DEFAULT '{}',\n                task_id TEXT,\n                parent_task_id TEXT,\n                UNIQUE(workspace, task_key)"
if old5 in dc:
    dc = dc.replace(old5, new5)
    dp.write_text(dc)
    print('[OK] db.py: task_id, parent_task_id columns added')
else:
    print('[WARN] db.py: pattern 5 not found')

print('Done')
