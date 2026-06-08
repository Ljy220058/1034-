"""Fix missing imports that cause collection errors."""
from pathlib import Path

PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Fix 1: models.py - missing field_validator import
models_path = PROJECT / 'backend' / 'models.py'
content = models_path.read_text()
old = 'from pydantic import BaseModel, Field'
new = 'from pydantic import BaseModel, Field, field_validator'
if old in content:
    content = content.replace(old, new)
    models_path.write_text(content)
    print('[OK] models.py: added field_validator import')
else:
    print('[WARN] models.py: pattern not found')

# Check for other common missing import issues
# Fix 2: models.py may also need field_validator in other files
for py_file in sorted((PROJECT / 'backend').rglob('*.py')):
    if py_file.name == '__init__.py':
        continue
    text = py_file.read_text()
    if 'field_validator' in text and 'from pydantic import' in text:
        if 'field_validator' not in text.split('from pydantic import')[1].split('\n')[0]:
            print(f'  [WARN] {py_file.relative_to(PROJECT)}: uses field_validator but may not import it')

print('Done')
