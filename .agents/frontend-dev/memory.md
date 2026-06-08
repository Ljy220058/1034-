# frontend-dev 记忆文件

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
- 2026-06-08：创意墙与热力面板可共用 frontend/api.js 的任务队列读取；本机可能没有 python3 命令，但可用 /root/miniconda3/bin/python 启动 http.server 并验证静态页。
- 2026-06-08：成员列表可由 frontend/member-list.js 动态补挂到 frontend/index.html；角色筛选若要和搜索、分页联动并保留状态，优先将 role 一并写入 localStorage，并在切换角色时走 `/api/v1/members?role=...` 后再做前端搜索过滤。
