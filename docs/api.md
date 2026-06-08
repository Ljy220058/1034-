# API 文档

本文档描述当前仓库中已经实现的后端接口。所有对外接口都以 `/api/v1` 为统一前缀，响应体统一包装在 `ApiResponse`（统一返回结构）中，业务数据放在 `data` 字段里。

## 1. 通用约定

### 1.1 Base URL

```text
http://localhost:8000/api/v1
```

### 1.2 请求与响应格式

- 请求体：`application/json`
- 响应体：`application/json`
- 时间字段：ISO 8601 字符串
- 认证方式：`Authorization: Bearer <access_token>`

### 1.3 通用返回结构

成功返回时，接口一般使用如下结构：

```json
{
  "data": {},
  "message": "成功"
}
```

出错时，接口返回标准 HTTP 状态码，并在 `detail` 中给出错误原因。例如：

```json
{
  "detail": "forbidden"
}
```

### 1.4 角色说明

系统支持以下角色：

- `member`：普通成员
- `leader`：团长或运营负责人
- `admin`：管理员

除注册接口外，角色提升只能由管理员或团长在后台执行。工作区健康、工作区任务板、空闲工人推荐和任务诊断接口也只允许 `leader` 和 `admin` 访问，普通成员无法查看这些共享工作区数据。

### 1.5 JWT 说明

JWT（JSON Web Token，身份令牌）在这个项目里是简化 token 字符串，不是标准签名 JWT。当前格式为 `member_id:role:expires_at`，例如：

```text
1:member:2026-06-13T08:30:00+00:00
```

### 1.6 工作区路径说明

工作区相关接口会校验 `workspace_path` 是否为绝对路径，并拒绝无效路径。

可接受的请求示例：

```text
GET /api/v1/workspaces/tasks/health?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab
```

如果参数不合法，接口会返回 `422`，常见错误信息包括：

- `工作区路径不合法`
- `invalid task status filter`
- `invalid task assignee filter`
- `invalid task sort field`
- `invalid deadline filter`

## 2. 数据模型

### 2.1 Member

```json
{
  "id": 1,
  "name": "张三",
  "phone": "13800000000",
  "role": "member",
  "running_years": 3,
  "pace": "5'30/km",
  "usual_distance_km": 10,
  "training_goal": "完成半马",
  "created_at": "2026-06-06T08:30:00+08:00",
  "updated_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.2 Announcement

```json
{
  "id": 3,
  "title": "周末活动通知",
  "body": "本周六晨跑照常进行。",
  "status": "published",
  "is_pinned": true,
  "created_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.3 Activity

```json
{
  "id": 10,
  "title": "周六晨跑",
  "start_time": "2026-06-08T07:00:00+08:00",
  "location": "人民公园东门",
  "route": "环湖 5 公里",
  "distance_km": 5,
  "pace_group": "5'30-6'00",
  "description": "适合新老成员一起参加",
  "created_at": "2026-06-06T08:30:00+08:00",
  "updated_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.4 Registration

```json
{
  "id": 88,
  "activity_id": 10,
  "member_id": 1,
  "status": "registered",
  "created_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.5 Attendance

```json
{
  "id": 12,
  "activity_id": 10,
  "member_id": 1,
  "status": "signed_in",
  "signed_in_at": "2026-06-08T06:58:00+08:00",
  "gps_checked": true
}
```

### 2.6 activity_participation_facts

`activity_participation_facts` 是 SQLite View（数据库视图），不是 HTTP API（HyperText Transfer Protocol Application Programming Interface，超文本传输协议应用程序接口）。
它把活动报名、签到状态和活动开始时间整理成一张只读分析表，适合做活动参与率统计和成员跑量排行。

```json
{
  "activity_id": 10,
  "member_id": 1,
  "activity_date": "2026-06-08",
  "registration_status": "registered",
  "attendance_status": "signed_in",
  "participation_status": "signed_in",
  "signed_in_at": "2026-06-08T06:58:00+08:00",
  "gps_checked": true,
  "registered_at": "2026-06-06T08:30:00+08:00",
  "activity_start_time": "2026-06-08T07:00:00+08:00"
}
```

#### 参数说明

| 字段 | 类型 | 说明 |
|------|------|------|
| activity_id | integer | 活动 ID |
| member_id | integer | 成员 ID |
| activity_date | date | 活动日期，由 `activities.start_time` 转换得到 |
| registration_status | string | 报名状态，来自 `registrations.status` |
| attendance_status | string | 签到状态，来自 `attendances.status` |
| participation_status | string | 参与状态：`signed_in`、`registered_unchecked`、`absent` 或 `cancelled` |
| signed_in_at | datetime | 签到时间；未签到时为空 |
| gps_checked | boolean | 是否通过 GPS（Global Positioning System，全球定位系统）校验 |
| registered_at | datetime | 报名记录创建时间 |
| activity_start_time | datetime | 活动开始时间 |

#### 成员跑量排行 SQL 示例

SQL（Structured Query Language，结构化查询语言）示例会把已签到成员按累计活动距离排序。
该查询已用本地数据验证过。

```sql
SELECT
    m.id AS member_id,
    m.name,
    COUNT(*) AS signed_in_activities,
    COALESCE(SUM(a.distance_km), 0) AS total_distance_km
FROM activity_participation_facts f
JOIN members m ON m.id = f.member_id
JOIN activities a ON a.id = f.activity_id
WHERE f.participation_status = 'signed_in'
GROUP BY m.id, m.name
ORDER BY total_distance_km DESC, signed_in_activities DESC, m.id ASC;
```

返回示例：

```json
[
  {
    "member_id": 2,
    "name": "Runner Ranking",
    "signed_in_activities": 1,
    "total_distance_km": 8.0
  }
]
```

#### 注意事项

- 当前仓库没有 `/api/v1/rankings` 或 `/api/v1/members/running-ranking` 这样的跑量排行接口。
- 当前仓库没有成员跑量排行可视化页面；前端如需展示排行，需要先新增只读接口。
- 已报名但未签到的记录会显示为 `registered_unchecked`，不应计入跑量。
- 活动距离来自 `activities.distance_km`；未填写距离的活动在排行中按 `0` 公里累计。

### 2.7 TaskQueueWorker

```json
{
  "id": 1,
  "worker_key": "worker-001",
  "name": "后端工人",
  "status": "active",
  "capabilities": ["api", "sqlite"],
  "last_seen_at": "2026-06-06T10:30:00+00:00",
  "created_at": "2026-06-06T10:00:00+00:00",
  "updated_at": "2026-06-06T10:30:00+00:00"
}
```

### 2.8 WorkspaceTaskBoard

`GET /api/v1/workspaces/workers/board` 的返回体放在 `data` 里，包含工人列表、任务快照和统计信息。

```json
{
  "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
  "workers": [],
  "snapshot": {
    "healthy": true,
    "summary": "0 任务，0 阻塞，0 过期"
  },
  "refresh": false,
  "recent_tasks": []
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |
| worker_filter | string | 否 | 按工人名称筛选结果 |
| refresh | boolean | 否 | 是否要求重新生成快照 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| workspace_path | string | 工作区绝对路径 |
| workers | array | 工人列表 |
| snapshot | object | 健康统计摘要 |
| refresh | boolean | 是否刷新快照 |
| worker_filter | string | 传入筛选条件时才出现 |
| recent_tasks | array | 最近任务快照，存在时才返回 |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：工作区路径不合法

### 2.9 WorkspaceTaskHealth

`GET /api/v1/workspaces/tasks/health` 会返回工作区任务健康统计，适合快速判断任务是否积压。

```json
{
  "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
  "counts": {
    "ready": 2,
    "running": 1,
    "blocked": 1,
    "done": 8
  },
  "summary": {
    "ready": 2,
    "running": 1,
    "blocked": 1,
    "done": 8,
    "total": 12
  }
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| workspace_path | string | 工作区绝对路径 |
| counts | object | 按状态统计的任务数量 |
| summary | object | 汇总统计，包含 total |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：工作区路径不合法

### 2.10 IdleWorkerRecommendations

`GET /api/v1/workspaces/idle-worker-recommendations` 会根据工作区任务和工人状态给出空闲工人建议。

```json
{
  "idle_workers": [
    {"name": "worker-a", "reason": "当前无运行中任务"}
  ],
  "recommendations": [
    {"worker": "worker-a", "task_key": "task-001", "reason": "优先级最高且负责人为空"}
  ]
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |
| limit | integer | 否 | 参与建议计算的最近任务数量，默认 20，最大 200 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| idle_workers | array | 空闲工人列表 |
| recommendations | array | 推荐分配结果 |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：工作区路径不合法

### 2.11 WorkspaceTaskDiagnostics

`GET /api/v1/workspaces/tasks/diagnostics` 会返回最近工作区任务的诊断建议，用于发现状态异常、负责人缺失和重复任务。

```json
{
  "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
  "limit": 100,
  "status_filter": null,
  "diagnostics": [
    {"severity": "warning", "message": "发现 1 个 blocked 任务"}
  ]
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |
| limit | integer | 否 | 检查的任务条数，默认 100，最大 500 |
| status_filter | string | 否 | 只检查某个任务状态 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| workspace_path | string | 工作区绝对路径 |
| limit | integer | 实际使用的检查上限 |
| status_filter | string/null | 传入的状态筛选条件 |
| diagnostics | array | 诊断建议列表 |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：工作区路径不合法

### 2.12 TaskItem

```json
{
  "task_key": "task-001",
  "title": "示例任务",
  "status": "todo",
  "description": "填写任务描述",
  "assignee": "张三",
  "priority": 1,
  "updated_at": "2026-06-06T10:30:00+00:00",
  "metadata": {}
}
```

### 2.13 TaskItemsTemplate

`GET /api/v1/task-items/template` 会返回一个可直接复制的任务导入模板。

```json
{
  "items": [
    {
      "task_key": "task-001",
      "title": "示例任务",
      "status": "todo",
      "description": "填写任务描述",
      "assignee": "张三",
      "priority": 1
    }
  ]
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 无 | - | - | 该接口无请求参数 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| items | array | 至少包含 1 条示例任务 |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`

### 2.14 TaskItemsCreate

`POST /api/v1/tasks/items` 会创建一条工作区任务项。

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/tasks/items' \
  -H 'Authorization: Bearer <access_token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
    "task_key": "task-001",
    "title": "示例任务",
    "status": "todo",
    "description": "填写任务描述",
    "assignee": "张三",
    "priority": 1
  }'
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |
| task_key | string | 是 | 任务唯一键 |
| title | string | 是 | 任务标题 |
| status | string | 是 | 任务状态：`todo`、`doing`、`done`、`blocked` |
| description | string | 是 | 任务说明 |
| assignee | string | 是 | 负责人姓名，必须存在于 task queue worker 列表 |
| priority | integer | 否 | 优先级，数值越大越优先 |

#### 返回示例

```json
{
  "data": {
    "task_key": "task-001",
    "title": "示例任务",
    "status": "todo",
    "description": "填写任务描述",
    "assignee": "张三",
    "priority": 1,
    "updated_at": "2026-06-06T10:30:00+00:00",
    "metadata": {}
  },
  "message": "成功"
}
```

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：工作区路径不合法、负责人不存在或任务状态不合法

### 2.15 TaskItemsBatchImport

`POST /api/v1/tasks/items/import` 和 `POST /api/v1/task-items/batch-import` 都支持批量导入任务项，两个接口返回结构一致。

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/tasks/items/import' \
  -H 'Authorization: Bearer <access_token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
    "items": [
      {
        "task_key": "task-001",
        "title": "示例任务",
        "status": "todo",
        "description": "填写任务描述",
        "assignee": "张三",
        "priority": 1
      }
    ]
  }'
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 绝对路径的工作区目录 |
| items | array | 是 | 任务项数组，不能为空 |

#### 返回示例

```json
{
  "data": {
    "count": 1,
    "items": [
      {
        "task_key": "task-001",
        "title": "示例任务",
        "status": "todo",
        "description": "填写任务描述",
        "assignee": "张三",
        "priority": 1,
        "updated_at": "2026-06-06T10:30:00+00:00",
        "metadata": {}
      }
    ]
  },
  "message": "成功"
}
```

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`
- `422`：`items` 为空、工作区路径不合法、负责人不存在、任务状态不合法或某一项格式不正确

### 2.16 WorkspaceScopedCreationHelper

`POST /api/v1/tasks/workspace-scoped-creation-helper` 会返回一组可去重的任务生成 payload，用于后续的 kanban 创建流程。

```json
{
  "count": 1,
  "tasks": [
    {
      "title": "中文任务标题",
      "description": "任务说明",
      "assignee": "docs-writer",
      "priority": 0,
      "idempotency_key": "example-key"
    }
  ]
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 无 | - | - | 该接口无请求体参数 |

#### 返回说明

| 字段 | 类型 | 说明 |
|------|------|------|
| count | integer | payload 数量 |
| tasks | array | 可直接用于后续创建的任务 payload |

#### 错误码

- `401`：未提供 Bearer token
- `403`：当前角色不是 `admin` 或 `leader`

### 2.17 常见业务接口

下面接口仍然是项目的核心业务接口，文档与返回结构保持一致：

- `GET /api/v1/auth/register`：注册新成员后返回 token
- `POST /api/v1/auth/login`：登录并返回 token
- `GET /api/v1/members`：查询成员列表
- `POST /api/v1/members`：创建成员
- `GET /api/v1/members/me`：查看当前登录成员资料
- `GET /api/v1/activities`：查询活动列表
- `POST /api/v1/activities`：创建活动
- `POST /api/v1/activities/{activity_id}/registrations`：报名活动
- `DELETE /api/v1/activities/{activity_id}/registrations/{member_id}`：取消报名
- `GET /api/v1/activities/{activity_id}/checkins`：查看签到记录
- `POST /api/v1/activities/{activity_id}/checkins`：成员签到
- `POST /api/v1/activities/{activity_id}/checkins/backfill`：管理员或团长补签
- `POST /api/v1/activities/{activity_id}/checkins/{attendance_id}/revoke`：撤销签到
- `GET /api/v1/announcements`：查询公告列表
- `POST /api/v1/announcements`：发布公告

#### 注意事项

- 大多数业务接口都要求先登录，再携带 `Authorization: Bearer <access_token>`。
- 当前仓库里，公告接口支持 `content`/`body` 两种字段名，最终都会归一到 `body`。
- 当前仓库里的 token 是服务端拼接的简化字符串，文档里不建议当作标准 JWT 解释。
- 工作区接口只读，不会修改任务状态；写入任务项的是 `tasks/items` 和批量导入接口。
- `workspace_path` 必须是能在当前机器上访问的绝对路径。
