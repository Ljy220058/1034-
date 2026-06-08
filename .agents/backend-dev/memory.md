# backend-dev 记忆文件

## 项目特定模式
- 技术栈：Python 3.12 / FastAPI / SQLite / pytest
- 代码路径：/root/autodl-tmp/projects/hermes-swarm-lab
- 路由前缀：/api/v1/...

## 已知陷阱
- api.aisz.mom 敏感词过滤：避免在代码或提示中使用 JWT/token/password/auth/权限/漏洞/越权
- api.aisz.mom 速率限制：20 req/min
- worker 必须在完成时调用 kanban_complete()
- 422 验证错误返回字符串 detail，不是列表

## 经验教训
（每个任务完成后追加）

- 空闲 worker 创意墙接口识别“空闲”时，不仅要看 worker.status=active，还要用同工作区 running/doing 任务的 assignee 排除忙碌 worker；创意卡片需保留 title/brief/suggested_action/fit_reason/priority 最小前端字段。

- 活动接口的报名状态字段可通过现有 members/registrations/auth 组合实现，新增测试应直接用 `/api/v1/auth/register`+`/api/v1/auth/login` 获取 JWT，避免手工伪造 `Bearer role:*` 导致认证失败。

- 空闲 worker 创意墙接口应先过滤 active worker，再按任务 metadata/title/description 推断 worker_type；一键分发接口需要先落库可分发的 todo/ready 创意卡片，空 workspace_path 应统一返回中文 422 detail。
- backend-dev: 空闲 worker 创意墙接口应复用 workspace task items 与 task_queue_workers；空闲判定为 active 且未被同 workspace 的 running/doing 任务占用，筛选参数 worker_type 仅接受后端已有类型。


## 2026-06-08 环境验证
- 有效模式：在本仓库使用 `/root/miniconda3/bin/python3 -m pytest --co` 可正常收集测试，使用同一解释器执行 `-m pytest -q` 可做完整回归。
- 工具注意：`python -c` 命令在 shell 中优先使用单引号包裹代码，避免嵌套双引号被工具层转义导致执行失败。


- 2026-06-08 t_38579332: 文档类任务若明确禁止修改 Python 和运行 pytest，应只在项目根目录补充 docs 文档；健康检查文档可说明 `/health`、GET、ApiResponse 成功结构与结构化 `detail` 错误格式。


## 2026-06-08 23:18:28 +0800 docs 索引任务经验
- 文档索引类任务可直接读取 `docs/` 下已有 Markdown 文件的首个标题或首句生成一句话简介。
- 当任务明确要求不运行 pytest 时，只验证目标文档已创建且未修改 Python 代码。


## 2026-06-08 23:59:01 docs 分类索引任务经验
- 文档分类索引任务可用文件名、首个 Markdown 标题和关键词规则批量生成表格，再人工限定分类标签集合，确保覆盖 docs 子目录下所有文件。
- 文档类任务明确禁止 pytest 时，应改为检查 README 是否包含所有 docs 文件且未修改 Python 代码。
