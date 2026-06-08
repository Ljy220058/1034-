# 创意任务与空闲 worker 分配使用指南

## 概述

本文档说明管理员或团长如何查看空闲 worker、创建中文创意任务、指定工作区，并根据任务状态验收结果。

适用场景：团队需要把文案、方案、海报说明或文档初稿等创意任务交给自动化 worker 处理。

本文使用的工作区固定为：

```text
dir:/root/autodl-tmp/projects/hermes-swarm-lab
```

`dir` 表示目录型工作区。worker 会在这个持久化目录中读取代码、写入文档或留下交接结果。

## 前置条件

你需要一个管理员或团长账号的 token（令牌）。后续示例统一使用环境变量保存请求地址、token 和工作区路径。

```bash
export BASE_URL='http://localhost:8000/api/v1'
export AUTH_HEADER='Authorization: Bearer your_token_here'
export WORKSPACE_PATH='/root/autodl-tmp/projects/hermes-swarm-lab'
```

token 是服务端识别当前用户身份的字符串。请求头必须写成 `Authorization: Bearer your_token_here`。

JWT（JSON Web Token，身份令牌）在很多系统里用于表达登录状态。本项目当前 token 是服务端生成的 Bearer token（持有者令牌），使用方式与 JWT 相同：谁持有 token，谁就能代表该用户发起请求。

## 相关概念

| 概念 | 说明 |
|------|------|
| worker | 执行任务的自动化工人，通常按能力标签接收任务 |
| 空闲 worker | 状态为 `active`，且当前没有 `running` 或 `doing` 任务的 worker |
| 创意任务 | 需要生成内容、文案、方案或说明的任务 |
| 工作区 | worker 执行任务时使用的目录，本文统一使用 `/root/autodl-tmp/projects/hermes-swarm-lab` |
| 任务状态 | 表示任务当前阶段的字段，例如 `todo`、`ready`、`running`、`doing`、`blocked`、`done` |
| metadata（元数据） | 给机器和人同时读取的附加 JSON 字段，适合放摘要、标签、验收结论和产物路径 |

## 快速开始

### 1. 登记一个可处理创意任务的 worker

这个接口用于创建或刷新 worker 信息。`capabilities` 是能力标签，后续推荐分配时会用它匹配任务标签。

```bash
curl -sS -X POST "$BASE_URL/task-queue/workers/intake" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "worker_key": "creative-writer-01",
    "name": "创意文案工人 01",
    "status": "active",
    "capabilities": ["创意", "文案", "活动策划"]
  }'
```

### 2. 导入一条中文创意任务元数据

这个接口用于批量校验和导入任务元数据。它会返回规范化后的任务信息。

```bash
curl -sS -X POST "$BASE_URL/tasks/items/import" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [
      {
        "task_key": "creative-dragon-boat-copy-001",
        "title": "生成端午跑步活动中文宣传语",
        "status": "todo",
        "description": "为端午跑步活动生成三条中文宣传语，并说明适合发布的渠道。",
        "assignee": null,
        "priority": 9,
        "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab"
      }
    ]
  }'
```

注意：`/tasks/items/import` 返回任务元数据，不等同于把任务写入 kanban 调度队列。需要真正派发给 worker 的任务，应由看板创建流程写入共享工作区任务表。

### 3. 查看空闲 worker 与推荐分配结果

这个接口会读取工作区任务快照，返回当前空闲 worker，以及可执行任务的推荐分配结果。

```bash
curl -sS "$BASE_URL/workspaces/idle-worker-recommendations?workspace_path=$WORKSPACE_PATH&limit=20" \
  -H "$AUTH_HEADER"
```

先看 `summary.idle_worker_count`。如果它是 `0`，说明当前没有可用的空闲 worker。

再看 `recommendations`。如果这里有记录，就可以按 `worker_key` 和 `task_id` 做后续分配。

### 4. 查看工作区 worker 看板

这个接口用于查看空闲 worker、忙碌 worker、已分配任务和最近变化。

```bash
curl -sS "$BASE_URL/workspaces/board?workspace_path=$WORKSPACE_PATH&refresh=true" \
  -H "$AUTH_HEADER"
```

如果只想查看某个 worker，可以加 `worker` 参数。

```bash
curl -sS "$BASE_URL/workspaces/board?workspace_path=$WORKSPACE_PATH&worker=creative-writer-01&refresh=true" \
  -H "$AUTH_HEADER"
```

## 接口说明

### 登记或刷新 worker

管理员或团长可以通过这个接口登记 worker。

#### 请求

`POST /api/v1/task-queue/workers/intake`

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| worker_key | string | 是 | worker 的唯一标识，例如 `creative-writer-01` |
| name | string | 是 | worker 的中文显示名称 |
| status | string | 否 | worker 状态，只能是 `active`、`paused` 或 `disabled` |
| capabilities | array[string] | 否 | 能力标签，例如 `创意`、`文案`、`活动策划` |

#### 返回示例

```json
{
  "data": {
    "id": 1,
    "worker_key": "creative-writer-01",
    "name": "创意文案工人 01",
    "status": "active",
    "capabilities": ["创意", "文案", "活动策划"],
    "last_seen_at": "2026-06-06T06:26:34.107862+00:00",
    "created_at": "2026-06-06T06:26:34+00:00",
    "updated_at": "2026-06-06T06:26:34.107862+00:00"
  },
  "message": "成功"
}
```

#### 错误

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或缺少 Bearer token |
| 403 | 当前账号不是管理员或团长 |
| 422 | worker 状态不合法，或请求体格式不正确 |

#### 注意事项

- `worker_key` 应保持稳定，不要用每次都会变化的随机值。
- `status=paused` 表示暂不参与分配。
- `status=disabled` 表示该 worker 不再接收任务。

### 导入中文创意任务元数据

管理员或团长可以通过批量导入接口提交任务元数据，并为任务指定工作区路径。

#### 请求

`POST /api/v1/tasks/items/import`

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| items | array[object] | 是 | 要导入的任务列表，不能为空 |
| items[].task_key | string | 是 | 任务唯一键，在同一批次中应保持唯一 |
| items[].title | string | 是 | 中文任务标题 |
| items[].status | string | 否 | 任务状态，支持 `todo`、`doing`、`done`、`blocked` |
| items[].description | string | 是 | 任务描述，说明要交付什么 |
| items[].assignee | string 或 null | 否 | 指定 worker；为空时表示尚未分配 |
| items[].priority | integer | 否 | 优先级，范围 `0` 到 `999`，数字越大越优先 |
| items[].workspace_path | string | 否 | 工作区路径，本文使用 `/root/autodl-tmp/projects/hermes-swarm-lab` |

#### 返回示例

```json
{
  "data": {
    "count": 1,
    "items": [
      {
        "task_key": "creative-dragon-boat-copy-001",
        "title": "生成端午跑步活动中文宣传语",
        "status": "todo",
        "description": "为端午跑步活动生成三条中文宣传语，并说明适合发布的渠道。",
        "assignee": null,
        "priority": 9,
        "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab"
      }
    ]
  },
  "message": "成功"
}
```

#### 错误

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或缺少 Bearer token |
| 403 | 当前账号不是管理员或团长 |
| 422 | `items` 为空、标题为空、描述为空、状态不合法或优先级不合法 |

#### 注意事项

- `title` 和 `description` 都应写中文，方便中文团队直接理解任务目标。
- `assignee` 为空时，任务还没有明确分配给某个 worker。
- `workspace_path` 建议固定为 `/root/autodl-tmp/projects/hermes-swarm-lab`，避免任务产物分散在多个目录。
- 该接口不保证任务进入派发队列；验收派发结果时应再查工作区看板。

### 查看空闲 worker 推荐

管理员或团长可以通过这个接口查看哪些 worker 当前可用，以及哪些任务适合分配给它们。

#### 请求

`GET /api/v1/workspaces/idle-worker-recommendations`

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 工作区路径，示例为 `/root/autodl-tmp/projects/hermes-swarm-lab` |
| limit | integer | 否 | 读取任务数量上限，范围 `1` 到 `200`，默认 `20` |

#### 返回示例

```json
{
  "data": {
    "source": "sqlite_workspace_snapshot",
    "summary": {
      "idle_worker_count": 1,
      "executable_task_count": 1,
      "recommendation_count": 1
    },
    "idle_workers": [
      {
        "worker_key": "creative-writer-01",
        "name": "创意文案工人 01",
        "status": "active",
        "capabilities": ["创意", "文案", "活动策划"],
        "idle_reason": "当前没有运行中的任务"
      }
    ],
    "allocation_strategy": {
      "strategy": "优先把高优先级创意任务分配给能力匹配的空闲 worker"
    },
    "recommendations": [
      {
        "worker_key": "creative-writer-01",
        "task_id": "creative-dragon-boat-copy-001",
        "reason": "worker 能力与任务标签匹配"
      }
    ],
    "executable_task_summaries": [
      {
        "task_id": "creative-dragon-boat-copy-001",
        "title": "生成端午跑步活动中文宣传语",
        "status": "todo",
        "priority": 9,
        "summary": "为端午跑步活动生成三条中文宣传语",
        "suggested_worker_key": "creative-writer-01",
        "reason": "worker 能力与任务标签匹配"
      }
    ],
    "risk_note": "路径参数已限制在工作区内，拒绝 ../、/etc/passwd、隐藏文件路径和非工作区文件访问，避免附件/文档路径穿越导致敏感文件泄露。"
  },
  "message": "成功"
}
```

#### 错误

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或缺少 Bearer token |
| 403 | 当前账号不是管理员或团长 |
| 422 | `workspace_path` 不合法，或 `limit` 超出允许范围 |

#### 注意事项

- `idle_worker_count` 表示当前空闲 worker 数量。
- `executable_task_count` 表示当前可分配任务数量。
- `recommendation_count` 表示系统给出的推荐数量。
- 推荐为空不一定是错误，可能是没有空闲 worker、没有待分配任务，或任务标签与 worker 能力不匹配。

### 查看工作区 worker 看板

管理员或团长可以通过这个接口查看空闲 worker、忙碌 worker、已分配任务和最近变化。

#### 请求

`GET /api/v1/workspaces/board`

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_path | string | 是 | 工作区路径，示例为 `/root/autodl-tmp/projects/hermes-swarm-lab` |
| worker | string | 否 | 只查看指定 worker，例如 `creative-writer-01` |
| refresh | boolean | 否 | 是否请求刷新快照，默认 `false` |

#### 返回示例

```json
{
  "data": {
    "workspace_path": "/root/autodl-tmp/projects/hermes-swarm-lab",
    "worker_filter": null,
    "refresh": true,
    "summary": {
      "idle_workers": 1,
      "busy_workers": 0,
      "assigned_tasks": 0,
      "recent_changes": 0
    },
    "idle_workers": [
      {
        "id": 1,
        "worker_key": "creative-writer-01",
        "name": "创意文案工人 01",
        "status": "active",
        "capabilities": ["创意", "文案", "活动策划"],
        "last_seen_at": "2026-06-06T06:26:34.107862+00:00",
        "created_at": "2026-06-06T06:26:34+00:00",
        "updated_at": "2026-06-06T06:26:34.107862+00:00"
      }
    ],
    "busy_workers": [],
    "assigned_tasks": [],
    "recent_changes": []
  },
  "message": "成功"
}
```

#### 错误

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或缺少 Bearer token |
| 403 | 当前账号不是管理员或团长 |
| 422 | 工作区路径不合法，或 worker 参数不合法 |

#### 注意事项

- `idle_workers` 有记录时，说明这些 worker 可以接收新任务。
- `busy_workers` 有记录时，说明这些 worker 正在处理 `running` 或 `doing` 任务。
- `assigned_tasks` 是已经分配并正在运行的任务。
- `recent_changes` 是工作区最近变化，可用于验收任务是否已经写入结果。

## 创建中文任务时如何指定工作区

创建创意任务时，任务说明里应同时写清楚工作区类型和路径。

推荐写法：

```text
工作区：dir:/root/autodl-tmp/projects/hermes-swarm-lab
交付物：在 docs/ 下新增或更新中文 Markdown 文档
验收方式：任务状态为 done，并在 metadata 或评论中写明文档绝对路径
```

如果使用看板创建工具，工作区参数应拆成两部分：

| 参数 | 值 | 说明 |
|------|----|------|
| workspace_kind | `dir` | 使用目录型工作区 |
| workspace_path | `/root/autodl-tmp/projects/hermes-swarm-lab` | worker 实际读写的项目目录 |

## 排查未派发任务

未派发通常表现为：任务已创建，但没有 worker 开始处理。

按下面顺序排查。

### 1. 确认是否有空闲 worker

```bash
curl -sS "$BASE_URL/workspaces/idle-worker-recommendations?workspace_path=$WORKSPACE_PATH&limit=20" \
  -H "$AUTH_HEADER"
```

查看 `summary.idle_worker_count`：

- 等于 `0`：没有空闲 worker，需要等待任务完成或登记新的 `active` worker。
- 大于 `0`：继续看任务是否可执行。

### 2. 确认推荐结果是否为空

继续查看同一个接口里的 `recommendation_count`：

- 等于 `0`：当前没有系统推荐的 worker 与任务组合。
- 大于 `0`：按 `recommendations` 中的 `worker_key` 和 `task_id` 继续处理。

推荐为空时，常见原因是任务没有进入工作区快照、任务状态不是 `todo` 或 `ready`、任务已经有负责人，或者能力标签不匹配。

### 3. 确认 worker 是否已经忙碌

```bash
curl -sS "$BASE_URL/workspaces/board?workspace_path=$WORKSPACE_PATH&refresh=true" \
  -H "$AUTH_HEADER"
```

查看 `summary.busy_workers` 和 `assigned_tasks`。

如果目标 worker 出现在 `busy_workers`，说明它正在处理任务，需要等待当前任务完成。

### 4. 确认工作区路径是否正确

工作区路径必须使用本文固定路径：

```text
/root/autodl-tmp/projects/hermes-swarm-lab
```

不要传 `../`、隐藏目录或项目外路径。服务端会拒绝不安全路径，避免读取敏感文件。

## 状态与验收说明

| 状态 | 含义 | 可以怎么处理 |
|------|------|--------------|
| todo | 已创建，等待处理 | 可以分配给空闲 worker |
| ready | 已准备好执行 | 可以优先分配给空闲 worker |
| running | 正在执行 | 等待 worker 写入结果 |
| doing | 正在执行 | 等待 worker 写入结果 |
| blocked | 被阻塞 | 先解决缺少的信息或依赖 |
| done | 已完成 | 查看 metadata、summary 或产物路径进行验收 |
| archived | 已归档 | 通常不再参与分配 |

验收时建议检查三项：

1. `status` 是否为 `done`。
2. `metadata.summary` 是否说明完成了什么。
3. `metadata.artifacts` 或任务评论中是否包含可打开的产物路径。

## 常见问题

### 为什么看不到空闲 worker？

可能没有登记 `active` worker，或者所有 `active` worker 都有运行中的任务。

先调用 `/task-queue/workers/intake` 登记 worker，再调用 `/workspaces/idle-worker-recommendations` 查看推荐结果。

### 为什么任务创建了但没有推荐？

可能原因包括：

- 任务状态不是 `todo` 或 `ready`。
- 任务已经有 `assignee`。
- 没有空闲 worker。
- 任务标签和 worker 能力标签不匹配。
- 任务只导入了元数据，还没有进入工作区任务快照。

### 如何判断任务已经验收完成？

优先看任务状态是否为 `done`，再看 `metadata.summary` 和产物路径。

如果没有摘要或产物路径，即使状态是 `done`，也建议人工复查任务评论或相关文档。
