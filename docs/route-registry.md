# 后端路由注册清单

本文档基于 `backend/routes/__init__.py` 与 `backend/app.py` 的实际注册关系整理，列出当前仓库中已挂载的后端路由、HTTP 方法、处理函数与简要说明。

## 总览

| 路径 | 方法 | 函数 | 说明 |
| --- | --- | --- | --- |
| `/` | GET | `root` | 返回后端运行提示。 |
| `/healthz` | GET | `healthz` | 返回基础健康状态、启动时间与版本。 |
| `/health` | GET | `health_check` | 返回完整 readiness 信息。 |
| `/health/ready` | GET | `readiness_check` | 返回 ready 判定与缺失项摘要。 |
| `/health/sync` | GET | `workspace_sync_healthcheck` | 返回同步场景下的健康检查数据。 |
| `/api/v1/activities` | GET | `list_activities` | 活动列表占位接口。 |
| `/api/v1/activities` | POST | `create_activity` | 创建活动占位接口。 |
| `/api/v1/activity_digest` | GET | `get_activity_digest` | 返回活动摘要占位数据。 |
| `/api/v1/activities/{activity_id}/photos` | POST | `upload_activity_photo` | 上传活动照片。 |
| `/api/v1/activities/{activity_id}/photos` | GET | `list_activity_photos` | 分页列出活动照片。 |
| `/api/v1/activities/{activity_id}/share-card` | GET | `share_card` | 生成活动分享卡片 PNG。 |
| `/api/v1/achievements/sample` | GET | `get_sample_achievements` | 返回成就样例与规则说明。 |
| `/api/v1/announcements` | GET | `read_announcements` | 读取公告列表。 |
| `/api/v1/announcements` | POST | `create_announcement_endpoint` | 创建公告。 |
| `/api/v1/announcements/{announcement_id}` | GET | `read_announcement` | 读取单条公告。 |
| `/api/v1/announcements/{announcement_id}` | PATCH | `patch_announcement` | 更新单条公告。 |
| `/api/v1/announcements/{announcement_id}` | DELETE | `remove_announcement` | 删除单条公告。 |
| `/api/v1/checkin-stats/{member_id}` | GET | `read_checkin_stats` | 获取成员签到统计。 |
| `/api/v1/checkin-heatmap/{member_id}` | GET | `read_checkin_heatmap` | 获取成员近一年签到热力图。 |
| `/api/v1/activities/{activity_id}/checkins` | GET | `read_activity_checkins` | 获取活动签到列表。 |
| `/api/v1/activities/{activity_id}/checkins` | POST | `create_checkin` | 创建活动签到。 |
| `/api/v1/activities/{activity_id}/checkins/{attendance_id}` | GET | `read_checkin` | 读取单条签到记录。 |
| `/api/v1/activities/{activity_id}/checkins/{attendance_id}` | DELETE | `delete_checkin` | 删除单条签到记录。 |
| `/api/v1/creative-cards/batch-route` | POST | `batch_route_creative_cards` | 批量路由创意卡片到 worker。 |
| `/api/v1/creative-cards/creative-task-generator` | GET | `read_creative_task_generator` | 获取创意任务生成器建议。 |
| `/api/v1/idle-task/recommendations` | GET | `recommend_idle_tasks` | 获取空闲任务推荐。 |
| `/api/v1/idle-task-summary/summary` | GET | `read_idle_task_summary` | 获取空闲任务摘要。 |
| `/api/v1/idle-task-summary/auto-prompts` | GET | `read_idle_card_auto_prompts` | 获取空闲卡片自动提醒。 |
| `/api/v1/idle-task-summary/sidebar` | GET | `read_idle_task_sidebar` | 获取侧边栏预览数据。 |
| `/api/v1/workers/creative-wall` | GET | `read_idle_worker_creative_wall` | 获取空闲 worker 创意墙。 |
| `/api/v1/workers/creative-wall/dispatch` | POST | `dispatch_idle_worker_creative_wall` | 一键分发空闲 worker 创意。 |
| `/api/v1/workers/heatmap` | GET | `read_worker_heatmap` | 获取 worker 任务热度图。 |
| `/api/v1/idle-idea-pool` | GET | `read_idle_worker_idea_pool` | 获取空闲 worker 创意池。 |
| `/api/v1/idle-ideas` | GET | `read_idle_worker_ideas` | 获取空闲 worker 创意建议。 |
| `/api/v1/idle-task-summary/summary` | GET | `read_idle_task_summary` | 获取空闲任务摘要。 |
| `/api/v1/idle-task-summary/auto-prompts` | GET | `read_idle_card_auto_prompts` | 获取空闲卡片自动提醒。 |
| `/api/v1/idle-task-summary/sidebar` | GET | `read_idle_task_sidebar` | 获取侧边栏预览数据。 |

## 注册来源

### `backend/routes/__init__.py`

`register_routes(app)` 通过 `app.include_router(...)` 注册了以下模块：

- `activities_router`
- `activity_digest_router`
- `achievements_router`
- `activity_photos_router`
- `announcements_router`
- `checkin_stats_router`
- `checkins_router`
- `creative_card_router`
- `creative_tasks_router`
- `idle_task_recommender_router`
- `idle_task_summary_router`
- `idle_worker_creative_wall_router`
- `idle_worker_heatmap_router`
- `idle_worker_idea_pool_router`
- `idle_worker_ideas_router`
- `idle_worker_summary_router`
- `idle_worker_task_heatmap_router`
- `login_verification_router`
- `member_activity_export_router`
- `member_ranking_router`
- `member_timeline_router`
- `members_router`
- `new_member_onboarding_router`
- `running_data_imports_router`
- `task_board_router`
- `task_board_intake_router`
- `task_imports_router`
- `tasks_router`
- `team_challenges_router`
- `training_pace_router`
- `training_plan_completion_router`
- `worker_dashboard_router`
- `worker_routing_recommendations_router`
- `workers_router`
- `workspaces_router`

### `backend/app.py`

`app.py` 除了调用 `register_routes(app)` 外，还额外单独挂载了：

- `activity_share_card_router`，也就是 `/api/v1/activities/{activity_id}/share-card`

## 备注

- `activity_share_card` 在当前代码里属于“重复注册”：它已经被 `backend/routes/__init__.py` 导入并在 `register_routes(app)` 中挂载，同时又在 `backend/app.py` 里单独 `include_router` 了一次。
- 文档中已按“实际可访问路由”列出，因此该接口只记一次到路径清单里，但在注册来源里单独说明了重复挂载。