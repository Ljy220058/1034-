from __future__ import annotations

from fastapi import FastAPI

from .app import app as _app

app = _app
