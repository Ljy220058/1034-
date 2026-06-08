# 1034 跑团社团网页管理系统

这是一个面向跑步社团的轻量级 Web 管理系统，也是 Hermes Swarm Lab 的协作实验仓库。
后端使用 FastAPI（Python Web 框架）提供 `/api/v1` 接口，前端是静态页面，数据存储使用 SQLite（轻量级关系型数据库）。

## 项目简介

这个项目主要解决跑团日常管理中的几类事情：

- 新成员注册并完善个人资料
- 团长和管理员维护成员、公告和活动
- 成员报名活动、取消报名并完成签到
- 运营人员基于报名、签到和活动距离数据生成成员跑量排行
- 管理员和团长查看共享工作区任务快照
- 部署环境通过健康检查确认服务是否正常运行
- 运营同学查看任务健康度看板，定位积压、重复失败、负责人过载和阻塞任务

如果你第一次接触仓库，建议先看这三份文档：

- `README.md`：项目总览、启动方式和目录结构
- `docs/user-guide.md`：面向成员、团长和管理员的使用说明
- `docs/api.md`：后端接口、请求字段、返回结构和权限说明

## 技术栈

- 后端：FastAPI（Python Web 框架）
- 数据存储：SQLite
- 前端：静态页面
- 部署：Docker + Nginx
- 测试：pytest

## 快速开始

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
- `migrations/004_activity_participation_indexes_and_view.sql`：活动参与率与跑量分析用的 SQLite View（数据库视图）和索引
- `scripts/seed_activity_participation.sql`：活动参与率与跑量排行的本地演示数据
- `deploy/nginx.conf`：Nginx 反向代理配置
- `scripts/start.sh`：统一启动脚本
- `tests/`：接口和前端测试

## 成员跑量排行数据来源

当前版本还没有单独的跑量排行 HTTP 接口，也没有专门的可视化页面。
后端已经提供 `activity_participation_facts` 数据库视图，方便后续实现图表或管理后台排行。

这个视图把报名、签到和活动开始时间合并成一张分析表。
成员跑量排行可以按 `participation_status = 'signed_in'` 过滤，
再把对应活动的 `distance_km` 求和。

可复制的本地查询示例：

```bash
python3 - <<'PY'
import sqlite3

db_path = './data/running_club.db'
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
    print(dict(row))
PY
```

注意事项：

- 只有已签到记录会计入跑量排行，已报名未签到不计入跑量。
- 活动没有填写 `distance_km` 时，计算结果会按 `0` 公里处理。
- 如果要做前端可视化，建议先新增只读 API，再让页面调用 API，不要让浏览器直接访问 SQLite。

## 跑团里程徽章生成器

仓库内置可重复运行的命令行工具 `scripts/generate_mileage_badges.py`，
用于从 SQLite 里的成员、活动和签到记录生成前端可直接消费的结构化 JSON。

徽章等级按累计已签到跑量判定：

| 等级 | 累计跑量阈值 |
| --- | ---: |
| 新手上路 | 1 km |
| 稳定打卡 | 20 km |
| 长距离达人 | 80 km |
| 跑团核心 | 200 km |

使用示例：

```bash
# 读取默认数据库：RUNNING_CLUB_DB_PATH 或 ./data/running_club.db
scripts/generate_mileage_badges.py --as-of 2026-06-06

# 指定数据库并写入文件
scripts/generate_mileage_badges.py --db ./data/running_club.db --as-of 2026-06-06 --output ./data/mileage_badges.json

# 基础自检：覆盖空数据、缺少字段、重复记录，输出稳定 JSON
scripts/generate_mileage_badges.py --self-check
```

输出 JSON 包含 `member_id`、`nickname`、`mileage.week_km`、`mileage.month_km`、`mileage.total_km`、`earned_badge`、`next_level_gap`。
脚本只统计 `attendances.status = 'signed_in'` 的记录；
同一成员同一活动的重复签到会去重；
缺少日期、缺少距离或非法负距离会被安全跳过。

## 重要环境变量

- `RUNNING_CLUB_DB_PATH`：SQLite 数据库路径
- `UVICORN_HOST`：监听地址，默认 `0.0.0.0`
- `UVICORN_PORT`：监听端口，默认 `8000`
- `UVICORN_WORKERS`：worker 数，默认 `1`

## 协作建议

本仓库的协作任务应尽量拆成明确、可验证的小工作项，例如：

- 先补接口文档，再补用户指南
- 先确认后端返回值，再写前端示例
- 先统一中文术语，再更新 README
