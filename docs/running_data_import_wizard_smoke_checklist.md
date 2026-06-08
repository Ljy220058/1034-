# 跑团导入向导冒烟测试清单

适用范围：跑步数据导入向导的高驰、佳明、CSV/JSON 文件导入、手动录入四类入口。本文用于快速冒烟，不依赖外部网络；第三方入口只验证授权预检、契约与中文提示，不访问真实平台。

## 一、已梳理路径

### 后端接口

| 入口 | 路径 | 方法 | 主要检查点 |
| --- | --- | --- | --- |
| 高驰授权预检 | `/api/v1/running-data-imports/precheck?source=coros` | GET | 来源枚举、授权说明、读取字段、隐私边界、授权凭据 `precheck_id` |
| 佳明授权预检 | `/api/v1/running-data-imports/precheck?source=garmin` | GET | 来源枚举、授权说明、读取字段、隐私边界、授权凭据 `precheck_id` |
| 导入启动占位 | `/api/v1/running-data-imports/start` | POST | 显式授权确认、预检凭据匹配、未授权拒绝、当前不真实写入 |
| CSV/JSON 向导 | `/api/v1/running-data-imports/wizard` | POST | 字段映射、缺失字段、预览行、重复活动 |
| 异常预检 | `/api/v1/running-data-imports/anomaly-precheck` | POST | 缺失时间、异常配速、重复轨迹、超长距离、空 GPS |

### 源码与测试路径

| 类型 | 路径 | 用途 |
| --- | --- | --- |
| 路由实现 | `backend/routes/running_data_imports.py` | 预检、启动、CSV/JSON 向导契约 |
| 异常预检测试 | `tests/test_running_data_import_anomaly_precheck.py` | 异常配速、重复轨迹、缺失时间样例 |
| 预检测试 | `tests/test_running_data_import_precheck.py` | 高驰/佳明/手动文件来源与授权门禁 |
| 向导测试 | `tests/test_running_data_import_wizard.py` | CSV/JSON 映射、重复活动、坏 JSON |
| 文案规则 | `backend/import_error_copy.py` | 导入错误中文提示统一规则 |
| 文案测试 | `tests/test_running_data_import_error_copy.py` | 缺少字段、格式错误、重复活动、权限不足、来源平台不支持 |
| 质量门禁文档 | `docs/running_data_import_wizard_quality_gate.md` | 更完整的发布前检查清单 |
| 前端入口现状 | `frontend/index.html`、`frontend/activity-waterfall.js` | 当前未发现明确导入向导页面或字段绑定实现，冒烟时需记录为移动端联动风险 |

## 二、执行命令

轻量冒烟命令：

```bash
pytest -q tests/test_running_data_import_precheck.py tests/test_running_data_import_wizard.py tests/test_running_data_import_anomaly_precheck.py tests/test_running_data_import_error_copy.py tests/test_running_data_import_smoke_checklist.py
```

发布前建议命令：

```bash
pytest -q tests/
pytest --cov=backend --cov-report=term
python -c "import backend.routes.running_data_imports; import backend.import_error_copy"
python scripts/check_import_error_copy.py
```

## 三、冒烟检查项

### SMOKE-01 高驰预检成功

- 入口：高驰。
- 操作：登录后请求 `GET /api/v1/running-data-imports/precheck?source=coros`。
- 预期结果：返回 200；`data.source.id` 为 `coros`；包含授权必需、读取字段、保存位置、撤销入口、隐私边界、`authorization_fields` 和 `consent_artifact.precheck_id`；`data.can_start_import=false`。
- 失败定位入口：优先查看 `backend/routes/running_data_imports.py` 的 `running_data_import_precheck`、`SUPPORTED_SOURCES`、`_precheck_id` 和 `_scope_version`。

### SMOKE-02 佳明预检成功

- 入口：佳明。
- 操作：登录后请求 `GET /api/v1/running-data-imports/precheck?source=garmin`。
- 预期结果：返回 200；`data.source.id` 为 `garmin`；读取字段不包含第三方账号密码、原始 token、密钥或无关隐私字段。
- 失败定位入口：优先查看 `backend/routes/running_data_imports.py` 的 `read_fields`、`privacy_boundary`。

### SMOKE-03 未登录访问被拒绝

- 入口：高驰、佳明、CSV/JSON 文件导入、手动录入。
- 操作：不带 `Authorization` 请求预检、启动或向导接口。
- 预期结果：返回 401；不得返回任何活动预览、授权范围或用户数据。
- 失败定位入口：优先查看 `backend/routes/common.py` 的登录依赖和路由函数的 `current_user` 依赖。

### SMOKE-04 未确认授权不能启动导入

- 入口：高驰、佳明、手动文件。
- 操作：登录后请求 `POST /api/v1/running-data-imports/start`，请求体中 `consent_acknowledged=false`。
- 预期结果：返回 403；提示用户需先确认导入授权范围；不得创建后台导入任务；请求体即使带有错误 `precheck_id` 也不能绕过该门禁。
- 失败定位入口：优先查看 `start_running_data_import` 的 `consent_acknowledged` 判断和 `backend/import_error_copy.py` 的权限不足文案。

### SMOKE-05 确认授权后只进入安全占位

- 入口：高驰、佳明、手动文件。
- 操作：登录后请求 `POST /api/v1/running-data-imports/start`，请求体中 `consent_acknowledged=true`，并提交与当前来源匹配的 `precheck_id`（例如 `running-data-imports:garmin:v1`）和 `scope_version=running-data-imports.v1`。
- 预期结果：返回 202；`data.import_started=false`；`data.status=authorized_precheck_only`；`data.authorized_scope.precheck_id` 与来源匹配；不写入真实活动。若 `precheck_id` 与 `source` 不一致，返回 403。
- 失败定位入口：优先查看 `start_running_data_import`，若返回真实写入状态需补充幂等、事务和重复策略测试；若错误凭据被接受需检查 `_precheck_id` 比对。

### SMOKE-06 非法来源返回可行动错误

- 入口：高驰、佳明、CSV/JSON 文件导入、手动录入。
- 操作：把 `source` 改为 `unknown_vendor` 请求预检、启动或向导。
- 预期结果：返回 422；错误信息包含允许值 `coros`、`garmin`、`generic`、`manual_file`。
- 失败定位入口：优先查看 `SUPPORTED_SOURCES` 与三个入口的非法来源处理是否一致。

### SMOKE-07 CSV 中文表头可识别

- 入口：CSV 文件导入。
- 操作：上传内容 `活动名称,开始时间,距离(km),用时(秒)` 的 CSV 到 `/wizard`。
- 预期结果：返回 200；`field_mapping.title=活动名称`；`field_mapping.start_time=开始时间`；预览行展示标题、开始时间、距离和时长。
- 失败定位入口：优先查看 `FIELD_ALIASES`、`_parse_csv`、`_detect_mapping`。

### SMOKE-08 JSON 英文字段可识别

- 入口：JSON 文件导入。
- 操作：上传包含 `name`、`startTime`、`distance`、`duration` 的 JSON 数组到 `/wizard`。
- 预期结果：返回 200；`input_format=json`；识别字段映射；预览行不丢失第二条及后续活动。
- 失败定位入口：优先查看 `_parse_json`、`FIELD_ALIASES`、`_build_preview`。

### SMOKE-09 缺少必填字段返回行级错误

- 入口：CSV/JSON 文件导入、手动录入。
- 操作：构造缺少活动名称或开始时间的导入内容。
- 预期结果：返回 200 且 `errors` 包含 `row`、`fields`、中文 `message`；`missing_fields` 标明缺失标准字段。
- 失败定位入口：优先查看 `_build_preview` 的行级错误和 `REQUIRED_FIELDS`。

### SMOKE-10 重复活动只标记不写入

- 入口：CSV/JSON 文件导入、手动录入。
- 操作：先创建同名且开始时间精确到分钟相同的活动，再用向导预览同一活动。
- 预期结果：预览行 `duplicate=true`；`duplicate_reason=活动已存在`；`duplicate_count` 等于重复行数量；向导阶段不新增活动。
- 失败定位入口：优先查看 `_existing_activity_keys` 和 `_build_preview`。

### SMOKE-11 异常配速被识别并给出中文建议

- 入口：CSV/JSON 文件导入、手动录入。
- 操作：上传 10 公里 1000 秒等明显异常配速样例到 `/anomaly-precheck`。
- 预期结果：返回 200；异常列表包含 `异常配速`；每条异常包含严重级别和修复建议。
- 失败定位入口：优先查看 `backend/running_data_anomaly_precheck.py` 和 `tests/test_running_data_import_anomaly_precheck.py`。

### SMOKE-12 移动端错误提示可行动

- 入口：移动端导入提示。
- 操作：分别模拟 400 坏 JSON、401 未登录、403 未确认授权、422 非法来源。
- 预期结果：移动端展示中文可行动提示；不得统一显示“服务器错误”；重复活动和缺失字段应能定位到具体行。
- 失败定位入口：当前项目未发现明确移动端导入页，先记录为前端/移动端联动风险；后续补齐入口后检查字段绑定：`authorization_required`、`read_fields`、`field_mapping`、`missing_fields`、`preview`、`duplicate_count`。

## 四、失败定位速查

| 失败现象 | 优先定位 |
| --- | --- |
| 返回 500 | 查看 `backend/routes/running_data_imports.py` 解析函数和全局异常处理 |
| 401 未生效 | 查看 `backend/routes/common.py` 登录依赖是否挂到路由 |
| 403 未生效 | 查看 `/start` 是否遗漏 `consent_acknowledged` 判断 |
| 422 不含允许值 | 查看 `SUPPORTED_SOURCES` 和非法来源错误文案 |
| CSV 中文表头识别失败 | 查看 `FIELD_ALIASES` 是否包含中文别名 |
| JSON 数组只解析一行 | 查看 `_parse_json` 的列表处理 |
| 重复活动未标记 | 查看 `list_activities` 返回字段和开始时间精确到分钟的去重键 |
| 异常配速未提示 | 查看异常预检规则阈值和字段映射 |
| 移动端提示不可行动 | 查看前端字段绑定和错误码分支；当前缺明确导入页时先补契约测试 |

## 五、最小通过标准

- 至少执行 SMOKE-01 到 SMOKE-12 中与本次改动相关的全部项目。
- 后端专项冒烟命令全绿。
- 所有用户可见提示保持中文且可行动。
- 不访问真实高驰、佳明或其他外部服务。
- 向导阶段只预览、标记和提示，不在未确认真实导入策略前写入新活动。
