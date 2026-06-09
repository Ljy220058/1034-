# 后端路径注册清单

本文档仅用于整理当前后端已注册的路径，不修改代码逻辑。

## 路由来源

- `backend/routes/__init__.py` 负责批量注册绝大多数业务路由。
- `backend/app.py` 额外直接挂载了 `activity_share_card` 路由，因此活动分享卡片也计入清单。

## 注册清单

| 路径 | 方法 | 处理函数 | 说明 |
|---|---|---|---|
| `/api/v1/activities` | GET | `list_activities` | 活动列表查询 |
| `/api/v1/activities/{activity_id}` | GET | `get_activity` | 单个活动详情 |
| `/api/v1/activities/{activity_id}/summary` | GET | `activity_summary` | 活动汇总信息 |
| `/api/v1/activities/{activity_id}/share-card` | GET | `share_card` | 服务端生成活动分享卡片 PNG |
| `/api/v1/activities/{activity_id}/photos` | GET | `list_activity_photos` | 活动照片列表 |
| `/api/v1/activities/{activity_id}/photos` | POST | `upload_activity_photo` | 上传活动照片 |
| `/api/v1/achievements/sample` | GET | `sample_achievements` | 成就样例数据 |
| `/api/v1/announcements` | GET | `list_announcements` | 公告列表 |
| `/api/v1/announcements/{announcement_id}` | GET | `get_announcement` | 公告详情 |
| `/api/v1/checkins` | GET | `list_checkins` | 签到记录列表 |
| `/api/v1/checkins` | POST | `create_checkin` | 创建签到记录 |
| `/api/v1/checkin-stats` | GET | `get_checkin_stats` | 签到统计 |
| `/api/v1/checkin-heatmap` | GET | `get_checkin_heatmap` | 签到热力图 |
| `/api/v1/creative-card` | GET | `creative_card` | 创意卡片 |
| `/api/v1/creative/tasks` | GET | `list_creative_tasks` | 创意任务列表 |
| `/api/v1/creative/tasks` | POST | `create_creative_task` | 创建创意任务 |
| `/api/v1/creative/recommendations` | GET | `creative_recommendations` | 创意推荐 |
| `/api/v1/creative/recommendations/sample` | GET | `creative_recommendations_sample` | 创意推荐示例 |
| `/api/v1/idle/tasks/recommendations` | GET | `recommend_idle_tasks` | 闲置任务推荐 |
| `/api/v1/idle/tasks/summary` | GET | `idle_task_summary` | 闲置任务汇总 |
| `/api/v1/idle/workers/creative-wall` | GET | `idle_worker_creative_wall` | 闲置成员创意墙 |
| `/api/v1/idle/workers/heatmap` | GET | `idle_worker_heatmap` | 闲置成员热力图 |
| `/api/v1/idle/workers/idea-pool` | GET | `idle_worker_idea_pool` | 闲置成员点子池 |
| `/api/v1/idle/workers/ideas` | GET | `idle_worker_ideas` | 闲置成员创意列表 |
| `/api/v1/idle/workers/summary` | GET | `idle_worker_summary` | 闲置成员汇总 |
| `/api/v1/idle/workers/task-heatmap` | GET | `idle_worker_task_heatmap` | 闲置成员任务热力图 |
| `/api/v1/login-verification` | GET | `login_verification` | 登录验证结果 |
| `/api/v1/member-activity-export` | GET | `member_activity_export` | 成员活动导出 |
| `/api/v1/member-ranking` | GET | `member_ranking` | 成员排行 |
| `/api/v1/member-timeline` | GET | `member_timeline` | 成员时间线 |
| `/api/v1/members` | GET | `list_members` | 成员列表 |
| `/api/v1/members` | POST | `create_member` | 创建成员 |
| `/api/v1/new-member-onboarding/status/{member_id}` | GET | `onboarding_status` | 新人引导状态 |
| `/api/v1/new-member-onboarding/pair` | POST | `pair_new_member` | 新人老带新配对 |
| `/api/v1/new-member-onboarding/welcome-checklist/{member_id}` | GET | `welcome_checklist` | 欢迎清单 |
| `/api/v1/running-data-imports` | POST | `running_data_imports` | 跑步数据导入 |
| `/api/v1/tasks` | GET | `list_tasks` | 任务列表 |
| `/api/v1/tasks` | POST | `create_task` | 创建任务 |
| `/api/v1/task-board` | GET | `task_board` | 任务看板 |
| `/api/v1/task-board/intake` | POST | `task_board_intake` | 看板收件箱 |
| `/api/v1/task-imports` | POST | `task_imports` | 任务导入 |
| `/api/v1/team-challenges` | GET | `list_team_challenges` | 团队挑战列表 |
| `/api/v1/team-challenges` | POST | `create_team_challenge` | 创建团队挑战 |
| `/api/v1/training-pace` | GET | `training_pace` | 训练配速建议 |
| `/api/v1/training-plan-completion` | GET | `training_plan_completion` | 训练计划完成度 |
| `/api/v1/worker-dashboard` | GET | `worker_dashboard` | 工作者仪表盘 |
| `/api/v1/worker-routing-recommendations` | GET | `worker_routing_recommendations` | 工作者路径推荐 |
| `/api/v1/workers` | GET | `list_workers` | 工作者列表 |
| `/api/v1/workspaces` | GET | `list_workspaces` | 工作区列表 |
| `/` | GET | `root` | 服务健康入口 |
| `/healthz` | GET | `healthz` | 基础健康检查 |
| `/health` | GET | `health_check` | 综合健康检查 |
| `/health/ready` | GET | `readiness_check` | 就绪检查 |
| `/health/sync` | GET | `workspace_sync_healthcheck` | 工作区同步健康检查 |

## 备注

- `/api/v1/activities/{activity_id}/share-card` 会返回 `image/png`，用于活动分享卡片的服务端 PNG 生成。
- 文档以当前 `backend/routes/__init__.py` 和 `backend/app.py` 的注册结果为准。
