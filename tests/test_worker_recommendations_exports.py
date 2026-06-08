from __future__ import annotations

from pathlib import Path

from backend.routes.worker_dashboard import _build_idle_summary
from backend.worker_recommendations import (
    default_worker_digest_workspace,
    list_queue_workers,
    worker_recommendations,
)


def test_worker_recommendations_exports_are_importable() -> None:
    """Ensure the worker recommendation helpers remain importable."""
    assert callable(worker_recommendations)
    assert callable(default_worker_digest_workspace)
    assert callable(list_queue_workers)


def test_build_worker_recommendations_returns_structured_payload() -> None:
    """Ensure recommendation payload contains expected keys."""
    payload = worker_recommendations(Path('/root/autodl-tmp/projects/hermes-swarm-lab'), limit=1)
    assert 'recommendations' in payload
    assert 'worker_count' in payload
    assert 'task_count' in payload
    assert isinstance(payload['recommendations'], list)


def test_worker_dashboard_summary_helper_is_available() -> None:
    """The worker routing module should be able to import the shared summary helper."""
    payload = _build_idle_summary('/root/autodl-tmp/projects/hermes-swarm-lab')
    assert 'summary' in payload
    assert 'dispatch_recommendations' in payload
