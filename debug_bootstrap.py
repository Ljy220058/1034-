import tempfile, sys, os
from pathlib import Path
sys.path.insert(0, '.')

import backend.database as database
from backend.app import app
from fastapi.testclient import TestClient

db_path = Path(tempfile.mkdtemp()) / 'test.db'
database.init_db(db_path)

from backend.database import connect
with connect() as conn:
    rows = conn.execute('SELECT * FROM members').fetchall()
    print(f'Members before startup: {len(rows)}')
print(f'DB_PATH before: {database.DB_PATH}')

client = TestClient(app, raise_server_exceptions=False)

print(f'DB_PATH after: {database.DB_PATH}')
with connect() as conn:
    rows = conn.execute('SELECT * FROM members').fetchall()
    print(f'Members after startup: {len(rows)}')

resp = client.post('/api/v1/auth/register', json={
    'name': 'Admin', 'phone': '13800000001', 'password': 'secret123', 'role': 'admin'
})
print(f'Admin status: {resp.status_code}, body: {resp.json()}')

import shutil
shutil.rmtree(db_path.parent)
