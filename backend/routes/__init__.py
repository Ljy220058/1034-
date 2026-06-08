from __future__ import annotations

from fastapi import FastAPI

from .activities import router as activities_router
from .activity_photos import router as activity_photos_router
from .activity_rules import router as activity_rules_router
from .achievements import router as achievements_router
from .announcements import router as announcements_router
from .checkin_stats import router as checkin_stats_router
from .checkins import router as checkins_router
from .creative_card_router import router as creative_card_router
from .creative_tasks import router as creative_tasks_router
from .idle_task_recommender import router as idle_task_recommender_router
from .idle_task_summary import router as idle_task_summary_router
from .idle_worker_creative_wall import router as idle_worker_creative_wall_router
from .idle_worker_heatmap import router as idle_worker_heatmap_router
from .idle_worker_idea_pool import router as idle_worker_idea_pool_router
from .idle_worker_ideas import router as idle_worker_ideas_router
from .idle_worker_summary import router as idle_worker_summary_router
from .idle_worker_task_heatmap import router as idle_worker_task_heatmap_router
from .member_activity_export import router as member_activity_export_router
from .member_ranking import router as member_ranking_router
from .members import router as members_router
from .new_member_onboarding import router as new_member_onboarding_router
from .running_data_imports import router as running_data_imports_router
from .task_board import router as task_board_router
from .task_board_intake import router as task_board_intake_router
from .task_imports import router as task_imports_router
from .tasks import router as tasks_router
from .training_pace import router as training_pace_router
from .training_plan_completion import router as training_plan_completion_router
from .worker_dashboard import router as worker_dashboard_router
from .worker_routing_recommendations import router as worker_routing_recommendations_router
from .workers import router as workers_router
from .workspaces import router as workspaces_router

router_modules = (
    members_router,
    activities_router,
    activity_photos_router,
    checkins_router,
    checkin_stats_router,
    announcements_router,
    task_board_intake_router,
    task_board_router,
    tasks_router,
    creative_card_router,
    creative_tasks_router,
    worker_dashboard_router,
    workers_router,
    workspaces_router,
    idle_task_recommender_router,
    idle_task_summary_router,
    idle_worker_summary_router,
    idle_worker_idea_pool_router,
    idle_worker_ideas_router,
    idle_worker_creative_wall_router,
    idle_worker_heatmap_router,
    idle_worker_task_heatmap_router,
    task_imports_router,
    activity_rules_router,
    member_activity_export_router,
    member_ranking_router,
    running_data_imports_router,
    training_pace_router,
    training_plan_completion_router,
    worker_routing_recommendations_router,
    achievements_router,
    new_member_onboarding_router,
)


def _routes_registered(app: FastAPI) -> bool:
    return bool(getattr(app.state, 'routes_registered', False))


def register_routes(app: FastAPI) -> None:
    if _routes_registered(app):
        return
    for route in router_modules:
        app.include_router(route)
    app.state.routes_registered = True
