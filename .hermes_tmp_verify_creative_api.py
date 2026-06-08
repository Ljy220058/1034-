from pathlib import Path
from uuid import uuid4
import json
from fastapi.testclient import TestClient
import backend.database as database
from backend.app import app

DB = Path('/root/autodl-tmp/projects/hermes-swarm-lab/data/docs_worker_verify_testclient.db')
database.init_db(DB)
client = TestClient(app, raise_server_exceptions=False)
phone = f'1555999-{uuid4().hex[:8]}'
register = client.post('/api/v1/auth/register', json={'name':'文档验证团长','phone':phone,'password':'secret123','role':'member'})
print('register', register.status_code)
member_id = register.json()['data']['member']['id']
with database.connect() as connection:
    connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', member_id))
login = client.post('/api/v1/auth/login', json={'phone':phone,'password':'secret123'})
print('login', login.status_code)
token = login.json()['data']['access_token']
headers = {'Authorization': f'Bearer {token}'}
workspace = '/root/autodl-tmp/projects/hermes-swarm-lab'

calls = []
resp = client.post('/api/v1/task-queue/workers/intake', json={'worker_key':'creative-doc-worker','name':'创意文案工人','status':'active','capabilities':['创意','文案']}, headers=headers)
calls.append(('worker_intake', resp))
resp = client.post('/api/v1/tasks/items/import', json={'items':[{'task_key':'creative-doc-task','title':'生成端午跑步活动创意','status':'todo','description':'为端午跑步活动生成三条中文宣传语','assignee':None,'priority':9,'workspace_path':workspace}]}, headers=headers)
calls.append(('task_import', resp))
resp = client.post('/api/v1/tasks/items', json={'task_key':'creative-board-task','title':'生成端午跑步活动创意','status':'todo','description':'为端午跑步活动生成三条中文宣传语','assignee':None,'priority':9}, headers=headers)
calls.append(('task_item_create', resp))
# Recommendation endpoint reads workspace_tasks snapshots. Seed one queue snapshot to verify response shape.
with database.connect() as connection:
    connection.execute(
        'INSERT INTO workspace_tasks(workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (workspace, 'creative-doc-task', '生成端午跑步活动创意', 'ready', None, 9, '2026-06-06T12:05:00+00:00', '{"summary":"为端午跑步活动生成三条中文宣传语","tags":["创意","文案"]}', 'creative-doc-task', None),
    )
resp = client.get('/api/v1/workspaces/board', params={'workspace_path':workspace,'worker':'creative-doc-worker','refresh':'true'}, headers=headers)
calls.append(('workspaces_board', resp))
resp = client.get('/api/v1/workspaces/idle-worker-recommendations', params={'workspace_path':workspace,'limit':20}, headers=headers)
calls.append(('idle_recommendations', resp))
resp = client.get('/api/v1/workspaces/tasks/board', params={'workspace_path':workspace,'status':'todo','limit':10}, headers=headers)
calls.append(('tasks_board', resp))

for name, resp in calls:
    print(name, resp.status_code)
    data = resp.json()
    print(json.dumps(data, ensure_ascii=False)[:1000])
    Path(f'/tmp/{name}_verified.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
