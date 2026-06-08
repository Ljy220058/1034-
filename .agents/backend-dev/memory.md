# backend-dev experience memory

- 2026-06-09: 新增只读统计接口时，优先沿用 `backend/routes/` + `ApiResponse` + 中文 `detail` 的现有模式，并在 `routes/__init__.py` 注册后，用独立 `tests/test_*.py` 覆盖正常、边界和缺失资源三类场景。
- 2026-06-09: 当前容器里 `python`/`python3` 不在 PATH，直接用 `python -m pytest` 会失败；需要先确认可用解释器路径再跑测试。
- 2026-06-09: `attendance` 统计接口实现中，按成员存在性先做 404，再用参数化 SQL 聚合 `signed_in_at`/`created_at` 日期，返回近 365 天日期桶更适合前端热力图。
