from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import team_challenges as team_challenges_module


DATA_FILE = Path(__file__).resolve().parent / 'team_challenges_test.json'


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_create_team_challenge_returns_api_response(tmp_path: Path, monkeypatch: object) -> None:
    """创建挑战接口应返回统一响应。"""
    monkeypatch.setattr(team_challenges_module, 'DATA_FILE', tmp_path / 'team_challenges.json')
    response = _client().post(
        '/api/v1/team-challenges/create',
        json={
            'title': '春季团队跑量挑战',
            'target_distance_km': 120,
            'start_date': '2026-06-01',
            'end_date': '2026-06-30',
            'team_count': 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '挑战创建成功'
    assert body['data']['title'] == '春季团队跑量挑战'
    assert body['data']['team_count'] == 3
    assert body['data']['members'] == []


def test_randomize_team_challenge_creates_balanced_assignments(tmp_path: Path, monkeypatch: object) -> None:
    """随机分队接口应生成分队结果。"""
    monkeypatch.setattr(team_challenges_module, 'DATA_FILE', tmp_path / 'team_challenges.json')
    DATA_FILE.write_text('', encoding='utf-8') if DATA_FILE.exists() else None
    _client().post(
        '/api/v1/team-challenges/create',
        json={
            'title': '春季团队跑量挑战',
            'target_distance_km': 120,
            'start_date': '2026-06-01',
            'end_date': '2026-06-30',
            'team_count': 3,
        },
    )

    response = _client().post(
        '/api/v1/team-challenges/randomize',
        json={'member_ids': [1, 2, 3, 4, 5, 6], 'team_count': 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '随机分队完成'
    assert len(body['data']['assignments']) == 3
    assert sorted(sum((team['member_ids'] for team in body['data']['assignments']), [])) == [1, 2, 3, 4, 5, 6]


def test_team_challenge_ranking_returns_structured_error_for_missing_challenge(tmp_path: Path, monkeypatch: object) -> None:
    """不存在的挑战应返回中文错误。"""
    monkeypatch.setattr(team_challenges_module, 'DATA_FILE', tmp_path / 'team_challenges.json')
    response = _client().get('/api/v1/team-challenges/ranking/1')

    assert response.status_code == 404
    assert response.json() == {'detail': '挑战不存在'}
