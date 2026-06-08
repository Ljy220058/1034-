from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from fastapi.routing import APIRoute

from backend.app import app, startup_event


def _route_method_keys() -> list[tuple[str, str]]:
    """返回应用中每个 APIRoute 的路径与方法组合。

    Returns:
        路由路径和 HTTP 方法组成的列表。
    """
    keys: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or set()):
            keys.append((route.path, method))
    return keys


def _duplicates(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """找出重复的路由方法组合。

    Args:
        items: 路由路径和 HTTP 方法组合。
    Returns:
        重复出现的路由方法组合列表。
    """
    counts = Counter(items)
    return sorted(key for key, count in counts.items() if count > 1)


def test_startup_does_not_register_duplicate_routes() -> None:
    """启动事件执行后不会新增重复的路径和方法。"""
    before = _route_method_keys()
    before_counts = Counter(before)

    startup_event()

    after = _route_method_keys()
    assert Counter(after) == before_counts
