from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import app

ICS_PREFIX = 'BEGIN:VCALENDAR'
ICS_SUFFIX = 'END:VCALENDAR'


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _extract_event_blocks(ics_text: str) -> list[list[str]]:
    lines = [line.strip() for line in ics_text.splitlines()]
    blocks: list[list[str]] = []
    current: list[str] = []
    inside = False
    for line in lines:
        if line == 'BEGIN:VEVENT':
            inside = True
            current = [line]
        elif line == 'END:VEVENT' and inside:
            current.append(line)
            blocks.append(current)
            inside = False
        elif inside:
            current.append(line)
    return blocks


def _assert_ics_event_has_fields(
    block: list[str],
    *,
    title: str,
    start: str,
    end: str,
    location: str | None,
    link: str | None,
    description_contains: str | None = None,
) -> None:
    text = '\n'.join(block)
    assert f'SUMMARY:{title}' in text
    assert f'DTSTART:{start}' in text
    assert f'DTEND:{end}' in text
    if location is None:
        assert 'LOCATION:' not in text
    else:
        assert f'LOCATION:{location}' in text
    if link is None:
        assert 'URL:' not in text
    else:
        assert f'URL:{link}' in text
    if description_contains is not None:
        assert description_contains in text


def test_training_plan_export_按开始时间排序_并输出合法ics且包含中文字段() -> None:
    client = _client()
    response = client.post('/api/v1/training-plan/export', json={
        'activities': [
            {
                'title': '晚间轻松跑',
                'start_time': '2026-06-08T19:30:00+08:00',
                'end_time': '2026-06-08T20:10:00+08:00',
                'location': '人民公园',
                'description': '配速放松，注意补水',
                'activity_url': 'https://example.com/活动/晚间轻松跑',
            },
            {
                'title': '晨跑训练',
                'start_time': '2026-06-07T06:30:00+08:00',
                'end_time': '2026-06-07T07:20:00+08:00',
                'location': '江边步道',
                'description': '中文说明：热身后分组跑',
                'activity_url': 'https://example.com/晨跑',
            },
        ]
    })

    assert response.status_code == 200
    data = response.json()['data']
    assert data['activity_count'] == 2
    assert data['content'].startswith(ICS_PREFIX)
    assert data['content'].strip().endswith(ICS_SUFFIX)
    assert '\r\n' in data['content']
    blocks = _extract_event_blocks(data['content'])
    assert len(blocks) == 2
    assert '晨跑训练' in '\n'.join(blocks[0])
    assert '晚间轻松跑' in '\n'.join(blocks[1])
    _assert_ics_event_has_fields(
        blocks[0],
        title='晨跑训练',
        start='20260606T223000Z',
        end='20260606T232000Z',
        location='江边步道',
        link=None,
        description_contains='中文说明：热身后分组跑',
    )
    assert 'https://example.com/晨跑' in '\n'.join(blocks[0])


def test_training_plan_export_空计划_仍输出合法ics壳() -> None:
    client = _client()

    response = client.post('/api/v1/training-plan/export', json={'activities': []})

    assert response.status_code == 200
    content = response.json()['data']['content']
    assert content.startswith(ICS_PREFIX)
    assert content.strip().endswith(ICS_SUFFIX)
    assert _extract_event_blocks(content) == []


def test_training_plan_export_end_time_早于_start_time_返回清晰错误() -> None:
    client = _client()

    response = client.post(
        '/api/v1/training-plan/export',
        json={
            'activities': [
                {
                    'title': '错误活动',
                    'start_time': '2026-06-08T10:00:00+08:00',
                    'end_time': '2026-06-08T09:30:00+08:00',
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'end_time 不能早于 start_time'
