from __future__ import annotations

from fastapi import FastAPI

from .activities import router as activities_router
from .activity_digest import router as activity_digest_router
from .achievements import router as achievements_router
from .activity_photos import router as activity_photos_router
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
from .login_verification import router as login_verification_router
from .member_activity_export import router as member_activity_export_router
from .member_ranking import router as member_ranking_router
from .members import router as members_router
from .new_member_onboarding import router as new_member_onboarding_router
from .running_data_imports import router as running_data_imports_router
from .task_board import router as task_board_router
from .task_board_intake import router as task_board_intake_router
from .task_imports import router as task_imports_router
from .tasks import router as tasks_router
from .team_challenges import router as team_challenges_router
from .training_pace import router as training_pace_router
from .training_plan_completion import router as training_plan_completion_router
from .worker_dashboard import router as worker_dashboard_router
from .worker_routing_recommendations import router as worker_routing_recommendations_router
from .workers import router as workers_router
from .workspaces import router as workspaces_router


def register_routes(app: FastAPI) -> None:
    """注册当前仓库中真实存在的路径模块。

    Args:
        app: FastAPI 应用实例。

    Returns:
        None。
    """
    app.include_router(activities_router)
    app.include_router(activity_digest_router)
    app.include_router(achievements_router)
    app.include_router(activity_photos_router)
    app.include_router(announcements_router)
    app.include_router(checkin_stats_router)
    app.include_router(checkins_router)
    app.include_router(creative_card_router)
    app.include_router(creative_tasks_router)
    app.include_router(idle_task_recommender_router)
    app.include_router(idle_task_summary_router)
    app.include_router(idle_worker_creative_wall_router)
    app.include_router(idle_worker_heatmap_router)
    app.include_router(idle_worker_idea_pool_router)
    app.include_router(idle_worker_ideas_router)
    app.include_router(idle_worker_summary_router)
    app.include_router(idle_worker_task_heatmap_router)
    app.include_router(login_verification_router)
    app.include_router(member_activity_export_router)
    app.include_router(member_ranking_router)
    app.include_router(members_router)
    app.include_router(new_member_onboarding_router)
    app.include_router(running_data_imports_router)
    app.include_router(task_board_router)
    app.include_router(task_board_intake_router)
    app.include_router(task_imports_router)
    app.include_router(tasks_router)
    app.include_router(team_challenges_router)
    app.include_router(training_pace_router)
    app.include_router(training_plan_completion_router)
    app.include_router(worker_dashboard_router)
    app.include_router(worker_routing_recommendations_router)
    app.include_router(workers_router)
    app.include_router(workspaces_router)
