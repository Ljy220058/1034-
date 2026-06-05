# 1034 跑团社团网页管理系统

这是一个面向跑步社团的轻量级 Web 管理系统，也是 Hermes Swarm Lab 的协作实验仓库。仓库当前包含 FastAPI 后端、静态前端、Docker 部署配置，以及一套面向新成员的中文文档。

## 项目定位

这个项目主要解决跑团日常管理中的几类事情：

- 让新成员快速注册并完善个人资料
- 让团长和管理员维护成员、公告和活动
- 让成员报名、取消报名、签到并查看自己的记录
- 让部署环境通过健康检查确认服务是否正常运行

如果你是第一次接触仓库，建议先看这三份文档：

- `README.md`：项目总览、启动方式和目录结构
- `docs/user-guide.md`：面向成员、团长和管理员的使用说明
- `docs/api.md`：后端接口、请求字段、返回结构和权限说明

## 核心功能

- 成员注册、登录、查看和维护个人资料
- 管理员 / 团长维护成员、公告和活动
- 活动报名、取消报名、签到与签到记录查询
- 提供健康检查接口，便于容器和部署环境确认服务状态

## 技术栈

- 后端：FastAPI
- 数据存储：SQLite
- 前端：静态页面
- 部署：Docker + Nginx
- 测试：pytest

## 持续集成

[![CI](https://github.com/your-org/your-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/your-repo/actions/workflows/ci.yml)

## 快速启动

### 本地启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export RUNNING_CLUB_DB_PATH=./data/running_club.db
./scripts/start.sh
```

启动后，后端通常会在 `http://localhost:8000` 提供服务。

### Docker 启动

```bash
docker compose up --build
```

启动后可访问：

- `http://localhost/`：Nginx 反向代理入口
- `http://localhost:8000/`：FastAPI 服务直连入口
- `http://localhost:8000/docs`：Swagger 接口文档
- `http://localhost:8000/redoc`：ReDoc 文档

## 目录结构

- `backend/`：FastAPI 后端实现
- `frontend/`：静态前端页面
- `docs/`：面向开发者和用户的中文文档
- `deploy/nginx.conf`：Nginx 反向代理配置
- `scripts/start.sh`：统一启动脚本

## 重要环境变量

- `RUNNING_CLUB_DB_PATH`：SQLite 数据库路径
- `UVICORN_HOST`：监听地址，默认 `0.0.0.0`
- `UVICORN_PORT`：监听端口，默认 `8000`
- `UVICORN_WORKERS`：worker 数，默认 `1`

## 协作建议

本仓库的协作任务应尽量拆成明确、可验证的小工作项，例如：

- 补充一个接口测试
- 修复一个前端交互问题
- 为某个部署脚本增加校验
- 补齐一段用户指南或 API 说明

如果要继续扩展功能，建议先更新文档，再补测试，最后改代码。

## 给 kanban 工人的工作区约定

本仓库的 kanban 任务默认在 `/root/autodl-tmp/projects/hermes-swarm-lab` 这个目录里执行。这个目录应视为共享的持久化工作区：后续 worker 可能会继续读取你留下的文档、代码、测试结果和备注，因此写入时要保持内容清晰、可复用、可追踪。

请遵守以下规则：

- 只在当前工作区内修改项目文件，不要把产物写到 `/root`、`/tmp`、家目录或其他项目外位置
- 只提交与当前任务相关的变更，避免把临时调试文件、下载缓存、日志碎片留在仓库根目录
- 如果必须生成临时文件，优先放在工作区内的临时子目录，并在任务完成前清理掉
- 需要交接给后续 worker 的内容，优先写进文档、任务评论或明确命名的文件，而不是散落在不相关位置

### 推荐的工作方式示例

假设你接到一个文档任务，可以这样组织工作：

1. 先在 `/root/autodl-tmp/projects/hermes-swarm-lab` 内查看现有 README、docs 和代码结构
2. 只修改相关文档，例如 `README.md`、`docs/api.md` 或 `docs/user-guide.md`
3. 如果新增说明或示例，确保路径写清楚，方便后续 worker 直接打开
4. 完成后在任务评论里写明输出路径，例如：
   `Output: /root/autodl-tmp/projects/hermes-swarm-lab/README.md, /root/autodl-tmp/projects/hermes-swarm-lab/docs/api.md`

总之，把这个目录当作团队共享的长期工作台，而不是一次性临时目录；这样后续的 kanban worker 才能快速接手并继续推进。
