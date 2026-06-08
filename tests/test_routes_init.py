from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes import register_routes


def test_register_routes_exposes_existing_modules() -> None:
    app = FastAPI()
    register_routes(app)
    client = TestClient(app)

    assert client.get('/api/v1/activities').status_code == 200
    assert client.get('/api/v1/activity_digest').status_code == 200
    assert client.get('/api/v1/training_plan_completion').status_code == 200
