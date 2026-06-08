The 1034 running club project uses Python FastAPI + 查询语句ite for the backend and a plain HTML/Vanilla JS/CSS frontend. The README is the first source of project requirements for this repo.
§
backend-dev: The repo uses FastAPI + 查询语句ite; several test commands may need an explicit interpreter path because pytest/python are not on PATH in this environment.
§
backend-dev: In this repo, tests may need an explicit Python interpreter path because pytest/python are not always on PATH in the environment.
§
backend-dev: 该仓库的 FastAPI 路径应统一返回 ApiResponse（data/message），并用中文结构化错误 detail；训练配速接口的实现应优先放在 backend/routes/ 下并通过 tests/ 下对应 pytest 覆盖正常值、范围值和无效输入。
§
The project 1034 uses FastAPI + 查询语句ite backend with ApiResponse-shaped JSON responses and Chinese structured error details; backend-dev tasks should read README.md and backend/app.py first, then add/adjust pytest coverage before completion.
§
backend-dev: 活动照片上传/列表接口采用 APIRouter(prefix='/api/v1/activities')、ApiResponse 成功体和中文 detail 错误；测试里可临时 monkeypatch 路径常量到 TemporaryDirectory，避免污染 uploads/photos。
§
backend-dev: 新人引导接口可复用 members、activities、attendances、member_groups 四张表；测试时用临时 sqlite 数据库并 monkeypatch 路径模块内的 DB_PATH，能稳定覆盖 status/pair/checklist 的 ApiResponse 结构。
§
backend-dev: 新增签到统计/热力图接口时，按 `attendances` 的 `signed_in_at` 做日期聚合，近 365 天热力图用日期桶输出 `{date, count}`；测试数据要避免违反 `attendances(activity_id, member_id)` 唯一约束，重复签到应放到不同 activity_id 上。
§
backend-dev: 团队跑量挑战接口可以用 JSON 文件做持久化，测试时 monkeypatch 模块级数据文件路径到临时目录，避免污染仓库内 data 目录；注册路由时要同步更新 backend/routes/__init__.py 的导入和 router_modules 列表。
