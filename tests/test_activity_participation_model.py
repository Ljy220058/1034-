from __future__ import annotations

from pathlib import Path

import backend.database as database


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'migrations' / '004_activity_participation_indexes_and_view.sql'
ROLLBACK = ROOT / 'migrations' / '004_activity_participation_indexes_and_view.rollback.sql'
SEED_SQL = ROOT / 'scripts' / 'seed_activity_participation.sql'


def _execute_script(path: Path) -> None:
    with database.connect() as connection:
        connection.executescript(path.read_text(encoding='utf-8'))


def test_activity_participation_migration_and_rollback_execute_cleanly(tmp_path: Path) -> None:
    database.init_db(tmp_path / 'participation-migration.db')

    _execute_script(MIGRATION)
    with database.connect() as connection:
        view = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' AND name = 'activity_participation_facts'"
        ).fetchone()
        registration_indexes = {row['name'] for row in connection.execute("PRAGMA index_list('registrations')")}
        attendance_indexes = {row['name'] for row in connection.execute("PRAGMA index_list('attendances')")}
        activity_indexes = {row['name'] for row in connection.execute("PRAGMA index_list('activities')")}

    assert view is not None
    assert 'idx_registrations_activity_status_member' in registration_indexes
    assert 'idx_registrations_member_status_activity' in registration_indexes
    assert 'idx_attendances_activity_status_member' in attendance_indexes
    assert 'idx_attendances_member_status_activity' in attendance_indexes
    assert 'idx_activities_start_time' in activity_indexes

    _execute_script(ROLLBACK)
    with database.connect() as connection:
        view = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' AND name = 'activity_participation_facts'"
        ).fetchone()
        registration_indexes = {row['name'] for row in connection.execute("PRAGMA index_list('registrations')")}
        attendance_indexes = {row['name'] for row in connection.execute("PRAGMA index_list('attendances')")}

    assert view is None
    assert 'idx_registrations_activity_status_member' not in registration_indexes
    assert 'idx_attendances_activity_status_member' not in attendance_indexes


def test_activity_participation_seed_data_covers_required_statuses(tmp_path: Path) -> None:
    database.init_db(tmp_path / 'participation-seed.db')
    _execute_script(MIGRATION)
    _execute_script(SEED_SQL)

    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT activity_id, member_id, activity_date, participation_status
            FROM activity_participation_facts
            WHERE activity_id = 9001
            ORDER BY member_id
            """
        ).fetchall()
        by_member = {row['member_id']: dict(row) for row in rows}

    assert {row['participation_status'] for row in rows} == {'signed_in', 'registered_unchecked', 'absent'}
    assert by_member[9002]['activity_date'] == '2026-06-08'
    assert by_member[9002]['participation_status'] == 'signed_in'
    assert by_member[9003]['participation_status'] == 'registered_unchecked'
    assert by_member[9004]['participation_status'] == 'absent'


def test_activity_participation_queries_use_expected_indexes(tmp_path: Path) -> None:
    database.init_db(tmp_path / 'participation-indexes.db')
    _execute_script(MIGRATION)
    _execute_script(SEED_SQL)

    with database.connect() as connection:
        by_activity_plan = '\n'.join(
            row['detail']
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT participation_status, COUNT(*)
                FROM activity_participation_facts
                WHERE activity_id = 9001
                GROUP BY participation_status
                """
            )
        )
        by_member_plan = '\n'.join(
            row['detail']
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT activity_id, participation_status
                FROM activity_participation_facts
                WHERE member_id = 9002
                ORDER BY activity_start_time DESC
                """
            )
        )
        by_date_plan = '\n'.join(
            row['detail']
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT activity_date, participation_status, COUNT(*)
                FROM activity_participation_facts
                WHERE activity_start_time >= '2026-06-01T00:00:00+00:00'
                  AND activity_start_time < '2026-07-01T00:00:00+00:00'
                GROUP BY activity_date, participation_status
                """
            )
        )

    assert 'idx_registrations_activity_status_member' in by_activity_plan
    assert 'idx_registrations_member_status_activity' in by_member_plan
    assert 'idx_activities_start_time' in by_date_plan
