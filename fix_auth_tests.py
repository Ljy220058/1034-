"""Fix auth tests for bootstrap era."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

path = PROJECT / 'tests' / 'test_auth.py'
content = path.read_text()

# Fix 1: test_auth_rejects_role_escalation_on_register
# Register member first, then admin should fail (with bootstrap + non-empty DB)
old1 = (
    "def test_auth_rejects_role_escalation_on_register(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    resp = client.post('/api/v1/auth/register', json={'name': 'Boss', 'phone': '13800000001', 'password': 'secret123', 'role': 'admin'})"
)
new1 = (
    "def test_auth_rejects_role_escalation_on_register(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    # bootstrap: register a regular member first so DB is not empty\n"
    "    _ = client.post('/api/v1/auth/register', json={'name': 'Regular', 'phone': '13800000000', 'password': 'secret123', 'role': 'member'})\n"
    "    resp = client.post('/api/v1/auth/register', json={'name': 'Boss', 'phone': '13800000001', 'password': 'secret123', 'role': 'admin'})"
)

if old1 in content:
    content = content.replace(old1, new1)
    print('[OK] test_auth.py: role escalation test fixed (register member first)')
else:
    print('[WARN] test_auth.py: pattern 1 not found')

# Fix 2: test_admin_can_manage_members - register with role='admin' explicitly
old2 = (
    "def test_admin_can_manage_members_but_cannot_escalate_roles_via_body(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000003', 'password': 'secret123'})"
)
new2 = (
    "def test_admin_can_manage_members_but_cannot_escalate_roles_via_body(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    # bootstrap: first user can be admin\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000003', 'password': 'secret123', 'role': 'admin'})"
)

if old2 in content:
    content = content.replace(old2, new2)
    print('[OK] test_auth.py: admin members test fixed (role=admin)')
else:
    print('[WARN] test_auth.py: pattern 2 not found')

# Fix 3: test_public_read_routes_and_admin_mutations
old3 = (
    "def test_public_read_routes_and_admin_mutations(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000006', 'password': 'secret123'})\n"
    "    assert admin_resp.status_code == 201"
)
new3 = (
    "def test_public_read_routes_and_admin_mutations(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    # bootstrap: first user can be admin\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000006', 'password': 'secret123', 'role': 'admin'})\n"
    "    assert admin_resp.status_code == 201"
)

if old3 in content:
    content = content.replace(old3, new3)
    print('[OK] test_auth.py: public routes test fixed (role=admin)')
else:
    print('[WARN] test_auth.py: pattern 3 not found')

# Fix 4: test_registration_self_service_and_forbidden_others
old4 = (
    "def test_registration_self_service_and_forbidden_others(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000007', 'password': 'secret123'})"
)
new4 = (
    "def test_registration_self_service_and_forbidden_others(tmp_path: Path) -> None:\n"
    "    client = _client(tmp_path)\n"
    "    # bootstrap: first user can be admin\n"
    "    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000007', 'password': 'secret123', 'role': 'admin'})"
)

if old4 in content:
    content = content.replace(old4, new4)
    print('[OK] test_auth.py: registration self-service test fixed (role=admin)')
else:
    print('[WARN] test_auth.py: pattern 4 not found')

path.write_text(content)
print('Done')
