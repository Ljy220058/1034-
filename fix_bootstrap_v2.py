"""Apply bootstrap auth fix with exact pattern from clean git."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Fix common.py bootstrap
cp = PROJECT / 'backend' / 'routes' / 'common.py'
cc = cp.read_text()

old = (
    "    if data.get('role') != ROLE_MEMBER:\n"
    "        if payload.__class__.__name__ == 'UserRegister':\n"
    "            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')\n"
    "        data['role'] = ROLE_MEMBER"
)

new = (
    "    if data.get('role') != ROLE_MEMBER:\n"
    "        if payload.__class__.__name__ == 'UserRegister':\n"
    "            # bootstrap: first user can be any role; reject escalation thereafter\n"
    "            from ..database import connect as _bc\n"
    "            with _bc() as _bconn:\n"
    "                _bcnt = _bconn.execute('SELECT COUNT(*) FROM members').fetchone()[0]\n"
    "            if _bcnt > 0:\n"
    "                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')\n"
    "        else:\n"
    "            data['role'] = ROLE_MEMBER"
)

if old in cc:
    cc = cc.replace(old, new)
    cp.write_text(cc)
    print('[OK] common.py: bootstrap logic applied')
else:
    print('[WARN] common.py: pattern not found')
    idx = cc.find("data.get('role') != ROLE_MEMBER")
    if idx > 0:
        print(repr(cc[idx:idx+250]))

print('Done')
