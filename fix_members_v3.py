"""Fix members route: skip UserRegister conversion, pass data directly."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

path = PROJECT / 'backend' / 'routes' / 'members.py'
content = path.read_text()

old = "    member = create_member(UserRegister(**payload.model_dump(exclude={'role'})))"
new = "    member_data = payload.model_dump(exclude={'role'})\n    member_data['password_hash'] = ''\n    member = create_member(**member_data)"

if old in content:
    content = content.replace(old, new)
    path.write_text(content)
    print('[OK] members.py: fixed admin member creation')
else:
    print('[WARN] pattern not found')

print('Done')
