"""Fix members route: create member, fetch record, return proper response."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

path = PROJECT / 'backend' / 'routes' / 'members.py'
content = path.read_text()

old_git = "    member = create_member(UserRegister(**payload.model_dump(exclude={'role'})))"
old_v3 = "    member_data = payload.model_dump(exclude={'role'})\n    member_data['password_hash'] = ''\n    member = create_member(**member_data)"

new = ("    import hashlib, secrets\n"
       "    member_data = payload.model_dump(exclude={'role'})\n"
       "    member_data['password_hash'] = ''\n"
       "    member_id = create_member(**member_data)\n"
       "    member = get_member(member_id)")

for old in [old_git, old_v3]:
    if old in content:
        content = content.replace(old, new)
        path.write_text(content)
        print('[OK] members.py: create + fetch member record')
        break
else:
    print('[WARN] no pattern found')
    idx = content.find('create_member(')
    if idx > 0:
        print(content[idx:idx+120])

print('Done')
