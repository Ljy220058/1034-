from __future__ import annotations

from fastapi import FastAPI

from .activities import router as activities_router
from .activity_digest import router as activity_digest_router
from .training_plan_completion import router as training_plan_completion_router


def register_routes(app: FastAPI) -> None:
    """注册当前仓库中真实存在的路径模块。

    Args:
        app: FastAPI 应用实例。

    Returns:
        None。
    """
    app.include_router(activities_router)
    app.include_router(activity_digest_router)
    app.include_router(training_plan_completion_router)
