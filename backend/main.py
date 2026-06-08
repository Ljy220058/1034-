from __future__ import annotations

from .app import app
from .routes import register_routes
from .settings import assert_within_workspace, detect_workspace_bootstrap

register_routes(app)

__all__ = ['app', 'assert_within_workspace', 'detect_workspace_bootstrap']
