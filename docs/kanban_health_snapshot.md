# 跑团任务运行健康快照脚本

## 目标

`scripts/kanban_health_snapshot.sh` 用于生成可直接复制到看板评论的中文 Kanban 任务运行健康快照，帮助调度者快速看到 running、todo/ready、blocked、长时间未完成任务的分布。

脚本只读读取 Hermes Kanban SQLite 数据库，或读取示例 JSON；不会修改线上调度配置，不会调用 `kanban_complete` / `kanban_block` / `kanban_comment`，不会杀进程。

## 一条命令运行

在项目根目录执行真实数据库快照：

```bash
scripts/kanban_health_snapshot.sh
```

显式指定数据库：

```bash
scripts/kanban_health_snapshot.sh --db /root/.hermes/kanban.db
```

如果当前环境没有 Python 命令但有 `uv`，脚本会自动使用 `uv run python`。

## 输出字段

每条任务摘要包含：

- 状态：running / ready / todo / blocked / triage，并输出中文标签。
- assignee：worker / profile 名称，未设置时显示“未分配”。
- 创建时间：`created_at`。
- 启动时间：`started_at`。
- 工作区路径：`workspace_path`。
- 是否可能超时：结合 `max_runtime_seconds`、running 时长、todo/ready/triage 等待时长判断。

## 快照四部分

输出固定包含四段，便于复制到看板评论：

1. 总体计数：关注任务总数、运行中、阻塞、可领取、待办、待细化、可能超时数量。
2. 按 worker 分组：每个 assignee 的任务数量、状态分布、任务明细。
3. 长时间 running / 长时间未完成提醒：列出超过阈值的任务。
4. 建议下一步动作：对 blocked、长时间 running、ready/todo 堆积给出处理建议。

## 阈值参数

默认阈值：

- running 超过 2 小时视为需要关注。
- todo / ready / triage 等待超过 24 小时视为需要关注。
- 如果任务设置了 `max_runtime_seconds`，优先使用该值判断 running 是否超过自身运行上限。

可通过环境变量或参数调整：

```bash
KANBAN_SNAPSHOT_LONG_RUNNING_HOURS=4 \
KANBAN_SNAPSHOT_TODO_AGE_HOURS=12 \
KANBAN_SNAPSHOT_LIMIT=500 \
scripts/kanban_health_snapshot.sh
```

或：

```bash
scripts/kanban_health_snapshot.sh --long-running-hours 4 --todo-age-hours 12 --limit 500
```

## 三种样例输出验证

示例数据位于：

```text
docs/kanban_health_snapshot_samples.json
```

### 1. 无异常样例

```bash
scripts/kanban_health_snapshot.sh \
  --sample-json docs/kanban_health_snapshot_samples.json \
  --scenario normal
```

预期：输出包含“未发现超过阈值的 running 或等待过久任务”。

### 2. 存在长时间 running / 长时间未完成样例

```bash
scripts/kanban_health_snapshot.sh \
  --sample-json docs/kanban_health_snapshot_samples.json \
  --scenario long_running
```

预期：输出“可能超时/长时间未完成”大于 0，并在第三部分列出 `t_long_001` / `t_long_002`。

### 3. 存在 blocked 样例

```bash
scripts/kanban_health_snapshot.sh \
  --sample-json docs/kanban_health_snapshot_samples.json \
  --scenario blocked
```

预期：总体计数中“阻塞”大于 0，第四部分提示“先处理 blocked”。

## 人工检查步骤

1. 执行语法检查：

```bash
bash -n scripts/kanban_health_snapshot.sh
```

2. 执行三种样例命令，确认均为中文输出，且包含：
   - “一、总体计数”
   - “二、按 worker 分组”
   - “三、长时间 running / 长时间未完成提醒”
   - “四、建议下一步动作”

3. 在 Hermes Kanban worker 环境中执行真实数据库快照：

```bash
HERMES_KANBAN_DB=/root/.hermes/kanban.db scripts/kanban_health_snapshot.sh
```

4. 将输出整体复制到目标任务的看板评论。

## 常见问题

- 数据库不存在：脚本会提示改用示例 JSON 验证，或设置 `--db /path/to/kanban.db`。
- 示例场景不存在：脚本会列出可选 scenario。
- 没有任务：快照仍会输出四部分，并提示当前没有关注任务。
