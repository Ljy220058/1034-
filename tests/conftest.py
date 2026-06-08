from __future__ import annotations

import os

os.environ.setdefault('RUNNING_CLUB_JWT_SECRET', 'pytest-running-club-secret-with-at-least-32-bytes')


def make_auth_headers(client, phone, role='member'):
    """Create auth headers by registering a user and upgrading role if needed.

    Idempotent: if user already exists, re-uses existing account.

    Args:
        client: FastAPI test client.
        phone: Phone number for the test user.
        role: Desired role (member, admin, leader).

    Returns:
        dict with Authorization header containing Bearer JWT token.
    """
    import backend.database as _db
    # Check if user already exists
    with _db.connect() as conn:
        existing = conn.execute('SELECT id, role FROM members WHERE phone = ?', (phone,)).fetchone()
    if existing is None:
        resp = client.post('/api/v1/auth/register', json={
            'name': f'Test{role.title()}', 'phone': phone, 'password': 'secret123', 'role': 'member',
        })
        assert resp.status_code == 201, f'Register failed: {resp.status_code} {resp.text}'
    if role != 'member':
        with _db.connect() as conn:
            conn.execute('UPDATE members SET role = ? WHERE phone = ?', (role, phone))
    login = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert login.status_code == 200, f'Login failed: {login.status_code} {login.text}'
    return {'Authorization': f'Bearer {login.json()["data"]["access_token"]}'}
