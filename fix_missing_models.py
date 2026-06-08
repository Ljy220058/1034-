"""Add missing model classes that repository.py imports but don't exist."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# Check what's missing from models.py
models_path = PROJECT / 'backend' / 'models.py'
content = models_path.read_text()

# Check what repository.py imports
imports_to_check = [
    'AnnouncementCreate', 'AnnouncementUpdate',
]

# Find where to add missing classes in models.py
# We'll add them after the last existing model class

missing = []
for name in imports_to_check:
    if f'class {name}' not in content:
        missing.append(name)
        print(f'MISSING: {name}')

if not missing:
    print('All models present')
else:
    # Read the DB schema for announcements to determine fields
    # From database.py: title TEXT, body TEXT, is_pinned INTEGER, status TEXT, created_at TEXT, updated_at TEXT
    announcement_models = '''
class AnnouncementCreate(BaseModel):
    """Announcement creation request body.

    Attributes:
        title: Announcement title.
        body: Announcement content body.
        is_pinned: Whether the announcement should be pinned.
        status: Publication status (draft or published).
    """

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    is_pinned: bool = False
    status: AnnouncementStatus | None = None


class AnnouncementUpdate(BaseModel):
    """Announcement update request body.

    Attributes:
        title: Updated title.
        body: Updated body.
        is_pinned: Updated pin status.
        status: Updated publication status.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    is_pinned: bool | None = None
    status: AnnouncementStatus | None = None
'''

    # Insert before the last model class or at a sensible location
    # Find a good insertion point — after TaskItemCreate or similar
    insert_marker = 'class TaskItemCreate(BaseModel):'
    if insert_marker in content:
        # Insert before TaskItemCreate
        content = content.replace(insert_marker, announcement_models + '\n' + insert_marker)
        models_path.write_text(content)
        print('Added AnnouncementCreate and AnnouncementUpdate to models.py')
    else:
        # Append at end
        content = content.rstrip() + '\n' + announcement_models + '\n'
        models_path.write_text(content)
        print('Appended AnnouncementCreate and AnnouncementUpdate to models.py')

    # Verify
    content2 = models_path.read_text()
    for name in imports_to_check:
        if f'class {name}' in content2:
            print(f'  [OK] {name} present')
        else:
            print(f'  [FAIL] {name} still missing')
