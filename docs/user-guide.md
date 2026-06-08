# 用户指南

本文档面向社团成员、团长和管理员，说明如何使用当前版本的跑团社团管理系统。若你是新加入项目的成员，可以先按“注册 → 登录 → 完善资料 → 查看活动 → 报名/签到”的顺序体验系统。

## 1. 登录与注册

### 1.1 注册新账号

如果你是新成员，可以先注册一个账号。注册时需要填写：

- 姓名
- 手机号
- 密码
- 跑龄
- 常用配速
- 常跑距离
- 训练目标

注册接口会默认创建普通成员账号，不能在注册时直接把自己设为管理员或团长。

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/auth/register' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "张三",
    "phone": "13800000000",
    "password": "secret123",
    "role": "member",
    "running_years": 3,
    "pace": "5'"'"'30/km",
    "usual_distance_km": 10,
    "training_goal": "完成半马"
  }'
```

### 1.2 登录

登录时输入手机号和密码即可。登录成功后，系统会返回一个 token（令牌）；后续请求都需要带上：

```http
Authorization: Bearer ***
```

如果你已经登录，但页面提示“未登录”或“无权限”，通常是 token 过期、复制错误或账号角色不足。

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{
    "phone": "13800000000",
    "password": "secret123"
  }'
```

## 2. 完善个人资料

登录后建议先检查自己的资料是否完整，尤其是：

- 姓名
- 跑龄
- 常用配速
- 常跑距离
- 训练目标

这些信息会影响成员列表展示、活动安排参考和统计结果。

### 填写建议

- 新手可以把训练目标写成“完成首个 5 公里”或“稳定完成 10 公里”。
- 有比赛计划的成员可以写明当前备赛方向，比如“半马备赛”。

## 3. 查看活动

进入活动页面后，你可以查看：

- 活动标题
- 开始时间
- 集合地点
- 路线
- 距离
- 配速组
- 活动描述

如果你不确定某次活动适不适合参加，优先看集合地点、距离和配速组，再决定是否报名。

#### 快速开始

```bash
curl -sS 'http://localhost:8000/api/v1/activities' \
  -H 'Authorization: Bearer ***'
```

## 4. 报名与取消报名

### 4.1 报名活动

当你决定参加某次活动时，打开活动详情页并提交报名。

报名后系统会记录你的状态。若重复报名同一活动，系统会返回冲突提示。

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/activities/10/registrations' \
  -H 'Authorization: Bearer ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "member_id": 1
  }'
```

### 4.2 取消报名

如果临时不能参加，请尽早取消报名，方便团长重新统计人数和调整配速分组。

#### 快速开始

```bash
curl -sS -X DELETE 'http://localhost:8000/api/v1/activities/10/registrations/1' \
  -H 'Authorization: Bearer ***'
```

## 5. 活动签到

到达集合地点后，可以进行签到。

### 签到时要注意

- 你必须已经报名该活动
- 通常需要由本人完成签到
- 如果开启了 GPS 校验，请允许定位权限
- 如果签到时间不在允许范围内，系统可能拒绝签到

### 签到失败时的排查顺序

1. 确认自己已经报名
2. 确认定位权限已打开
3. 确认网络正常
4. 确认当前位置与活动地点足够接近
5. 重新提交签到

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/activities/10/checkins' \
  -H 'Authorization: Bearer ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "member_id": 1,
    "activity_id": 10,
    "gps_checked": true
  }'
```

## 6. 查看公告

管理员和团长可以发布公告，成员登录后可以看到：

- 活动提醒
- 活动变更通知
- 欢迎新成员
- 其他社团通知

如果页面上有置顶公告，建议先看置顶内容，再看普通公告。

#### 快速开始

```bash
curl -sS 'http://localhost:8000/api/v1/announcements?status=published' \
  -H 'Authorization: Bearer ***'
```

## 7. 查看个人信息

你可以在“我的资料”页面查看当前账号信息，包括：

- 姓名
- 手机号
- 角色
- 跑龄
- 配速
- 常跑距离
- 训练目标

如果这些内容有误，请联系管理员修改。

#### 快速开始

```bash
curl -sS 'http://localhost:8000/api/v1/members/me' \
  -H 'Authorization: Bearer ***
```

### 7.1 查看成员跑量排行

当前版本没有单独的前端排行页面，但管理员或团长可以先用本地数据库查看成员跑量排行。
排行依据是 `activity_participation_facts` 视图，统计已签到活动的距离总和。

#### 快速开始

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path

db_path = Path('./data/running_club.db')
with sqlite3.connect(db_path) as connection:
    connection.row_factory = sqlite3.Row
    rows = connection.execute('''
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
        ORDER BY total_distance_km DESC, signed_in_activities DESC, m.id ASC
    ''').fetchall()

for row in rows:
    print(f"{row['member_id']}\t{row['name']}\t{row['signed_in_activities']} 场\t{row['total_distance_km']} km")
PY
```

### 7.2 工作区任务发现接口

如果你是管理员或团长，还可以查看共享工作区中的任务快照。

- 接口：`GET /api/v1/workspaces/tasks`
- 必填参数：`workspace_path`
- 可选参数：`limit`、`status`
- 返回结果按最近更新时间倒序排列
- 只有 `admin` 和 `leader` 可以访问

常见用法：

```http
GET /api/v1/workspaces/tasks?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab&limit=10&status=running
```

如果参数不合法，通常会看到以下错误：

- `invalid workspace path`
- `invalid task status filter`

这个接口适合在多人协作时快速确认某个工作区里有哪些任务正在运行、是否已经完成，以及最近是谁更新了任务。

### 7.2 工作区任务板接口

如果你是管理员或团长，还可以查看更细的任务板快照。这个接口支持筛选、排序和统计。

- 接口：`GET /api/v1/workspaces/tasks/board`
- 必填参数：`workspace_path`
- 可选参数：`status`、`limit`
- 只有 `admin` 和 `leader` 可以访问

常见用法：

```http
GET /api/v1/workspaces/tasks/board?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab&status=running&limit=10
```

这个接口会返回任务列表、过滤条件、统计信息和 worker 可用性摘要。你可以把它理解成“带筛选条件的任务看板快照”。

### 7.3 Task queue worker 列表

如果你是管理员或团长，还可以查看任务队列 worker 列表。这个列表显示当前登记的 worker 名称、状态和能力标签。

- 接口：`GET /api/v1/task-queue/workers`
- 只有 `admin` 和 `leader` 可以访问

#### 快速开始

```bash
curl -sS 'http://localhost:8000/api/v1/task-queue/workers' \
  -H 'Authorization: Bearer ***'
```

### 7.4 Task queue worker 登记

管理员或团长可以登记或更新一个 worker。常见场景是记录一个新的自动化 worker，或者更新它的状态。

- 接口：`POST /api/v1/task-queue/workers/intake`
- 请求体需要 `worker_key`、`name`、`status`，`capabilities` 可选
- `status` 只能是 `active`、`paused` 或 `disabled`

#### 快速开始

```bash
curl -sS -X POST 'http://localhost:8000/api/v1/task-queue/workers/intake' \
  -H 'Authorization: Bearer ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "worker_key": "worker-001",
    "name": "后端工人",
    "status": "active",
    "capabilities": ["api", "sqlite"]
  }'
```

## 8. 团长和管理员怎么用

除了社团业务操作外，团长和管理员还可以查看共享工作区中的任务快照，用来快速了解文档、代码或测试任务的进度。

如果你是团长或管理员，通常按照这个顺序操作最顺手：

1. 先创建或维护成员资料
2. 再创建活动
3. 在活动前检查报名人数
4. 活动当天检查签到情况
5. 活动结束后再发布公告或总结

### 你可以做的管理操作

- 创建、编辑和删除活动
- 创建、编辑和删除公告
- 查看成员列表
- 查看活动签到记录
- 修改成员资料
- 删除普通成员账号
- 通过 `/api/v1/workspaces/tasks` 查看共享工作区任务列表
- 通过 `/api/v1/workspaces/tasks/board` 查看带筛选条件的任务板
- 查看和登记 task queue worker

注意：普通成员不能把自己的角色改成管理员或团长，也不能替别人越权操作。

### 查看工作区任务时需要注意什么？

- 你需要管理员或团长权限
- `workspace_path` 必须是有效路径，服务端会标准化为绝对路径
- 任务列表默认按最近更新时间排序，方便快速找到最新变更
- 如果你只想看某一种状态，可以传 `status=running`、`status=done` 之类的过滤条件
- 任务板接口还能按状态筛选

## 9. 常见问题

### 为什么我看不到成员列表？

成员列表通常只对管理员和团长开放。普通成员只能看自己的资料。

### 为什么我报名后又变成未报名？

可能是页面没有刷新，或者你点到了取消报名按钮。建议重新打开活动详情页确认状态。

### 为什么签到一直失败？

最常见的原因是：

- 没有先报名
- 不在允许签到时间内
- 定位权限没开
- 当前位置离活动地点太远

### 为什么看不到统计数据？

当前版本主要提供核心业务接口，统计能力可能还在补充中。请以页面实际显示为准。
