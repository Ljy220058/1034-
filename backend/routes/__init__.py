from __future__ import annotations

from importlib import import_module
from typing import Iterable

from fastapi import FastAPI

ROUTER_MODULE_NAMES = (
    'activities',
    'activity_digest',
    'activity_photos',
    'activity_rules',
    'achievements',
    'announcements',
    'checkin_stats',
    'checkins',
    'creative_card_router',
    'creative_tasks',
    'idle_task_recommender',
    'idle_task_summary',
    'idle_worker_creative_wall',
    'idle_worker_heatmap',
    'idle_worker_idea_pool',
    'idle_worker_ideas',
    'idle_worker_summary',
    'idle_worker_task_heatmap',
    'member_activity_export',
    'member_ranking',
    'members',
    'new_member_onboarding',
    'running_data_imports',
    'task_board',
    'task_board_intake',
    'task_imports',
    'tasks',
    'team_challenges',
    'training_pace',
    'training_plan_completion',
    'worker_dashboard',
    'worker_routing_recommendations',
    'workers',
    'workspaces',
)


def _load_router_modules(module_names: Iterable[str]) -> list[object]:
    """加载可用的路由模块。

    Args:
        module_names: `backend.routes` 下的模块名列表。

    Returns:
        带有 `router` 属性的模块列表。
    """
    loaded_modules: list[object] = []
    for module_name in module_names:
        module = import_module(f'.{module_name}', __name__)
        router = getattr(module, 'router', None)
        if router is None:
            continue
        loaded_modules.append(router)
    return loaded_modules


router_modules = _load_router_modules(ROUTER_MODULE_NAMES)


def _routes_registered(app: FastAPI) -> bool:
    return bool(getattr(app.state, 'routes_registered', False))


def register_routes(app: FastAPI) -> None:
    if _routes_registered(app):
        return
    for route in router_modules:
        app.include_router(route)
    app.state.routes_registered = True
