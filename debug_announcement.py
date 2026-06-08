import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')

import backend.database as database
from backend.app import app
from fastapi.testclient import TestClient

db_path = Path(tempfile.mkdtemp()) / 'test.db'
database.init_db(db_path)
client = TestClient(app, raise_server_exceptions=False)

r = client.post('/api/v1/auth/register', json={
    'name': 'Admin', 'phone': '13801', 'password': 'secret123', 'role': 'admin'
})
print(f'Register: {r.status_code}')

if r.status_code == 201:
    token = r.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    r2 = client.post('/api/v1/announcements', json={
        'title': 'Test', 'body': 'Hello'
    }, headers=headers)
    print(f'Announce: {r2.status_code}')
    if r2.status_code >= 500:
        print(f'Body: {r2.text[:500]}')
    else:
        print(f'Body: {r2.json()}')
else:
    print(f'Register error: {r.json()}')

import shutil
shutil.rmtree(db_path.parent)
