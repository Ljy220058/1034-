from __future__ import annotations

import json
from pathlib import Path

from backend.seed_data import build_seed_pack, export_seed_pack, iter_seed_rows


def test_build_seed_pack_is_deterministic() -> None:
    first = build_seed_pack()
    second = build_seed_pack()

    assert first == second
    assert first.members[0]['name'] == 'Li Ming'
    assert first.activities[0]['title'] == 'Tuesday Track Tempo'
    assert first.announcements[0]['is_pinned'] == 1


def test_seed_pack_contains_expected_rows() -> None:
    pack = build_seed_pack()

    assert len(pack.members) == 4
    assert len(pack.activities) == 3
    assert len(pack.registrations) == 6
    assert len(pack.attendances) == 4
    assert len(pack.announcements) == 2
    assert {row['status'] for row in pack.registrations} == {'registered', 'cancelled'}
    assert {row['status'] for row in pack.attendances} == {'signed_in', 'absent'}


def test_iter_seed_rows_preserves_table_grouping() -> None:
    rows = list(iter_seed_rows())

    assert [table for table, _ in rows[:4]] == ['members'] * 4
    assert [table for table, _ in rows[4:7]] == ['activities'] * 3
    assert [table for table, _ in rows[7:13]] == ['registrations'] * 6
    assert [table for table, _ in rows[13:17]] == ['attendances'] * 4
    assert [table for table, _ in rows[17:]] == ['announcements'] * 2


def test_export_seed_pack_writes_json(tmp_path: Path) -> None:
    output_path = tmp_path / 'seed-pack.json'

    result = export_seed_pack(output_path)

    assert result == output_path
    data = json.loads(output_path.read_text(encoding='utf-8'))
    assert data['members'][0]['phone'] == '15550010001'
    assert data['activities'][1]['distance_km'] == 16.0
    assert data['announcements'][0]['status'] == 'published'
