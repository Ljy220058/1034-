from __future__ import annotations

from fastapi import APIRouter

from .activities import router as activities_router
from .announcements import router as announcements_router
from .auth import router as auth_router
from .checkins import router as checkins_router
from .members import router as members_router
from .tasks import router as tasks_router
from .workspaces import router as workspaces_router

router_modules = (
    auth_router,
    members_router,
    announcements_router,
    tasks_router,
    activities_router,
    checkins_router,
    workspaces_router,
)


def register_routes(app) -> None:
    for route in router_modules:
        app.include_router(route)
