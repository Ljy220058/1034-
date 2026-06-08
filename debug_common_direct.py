import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')

import backend.database as database
db_path = Path(tempfile.mkdtemp()) / 'test.db'
database.init_db(db_path)
print(f'DB_PATH: {database.DB_PATH}')

# Direct call to sanitize_member_payload
from backend.routes.common import sanitize_member_payload
from fastapi import HTTPException

# Simulate a UserRegister
class FakePayload:
    pass

fake = FakePayload()
fake.__class__.__name__ = 'UserRegister'

def model_dump(exclude=None, exclude_unset=False):
    return {'name': 'Admin', 'phone': '13801', 'role': 'admin'}
fake.model_dump = model_dump

try:
    result = sanitize_member_payload(fake)
    print(f'Result: {result}')
except HTTPException as e:
    print(f'HTTPException: {e.status_code} {e.detail}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')

import shutil
shutil.rmtree(db_path.parent)
