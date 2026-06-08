# 跑步数据导入向导质量门禁清单

适用范围：跑步数据导入预检与向导接口，当前重点文件包括 `backend/routes/running_data_imports.py`、`backend/import_error_copy.py`、`tests/test_running_data_import_precheck.py`、`tests/test_running_data_import_wizard.py`，以及后续移动端导入入口。

执行原则：本清单是轻量质量门禁准备项，不要求暂停正在运行的开发任务；开发任务完成后，QA Gate 可按本清单抽查接口契约、错误码、重复识别、中文文案、移动端展示联动与回归范围。

## 一、必须检查项

### 1. 预检接口契约稳定

检查对象：`GET /api/v1/running-data-imports/precheck?source=<source>`。

通过标准：
- 已登录用户请求支持的来源时返回 200。
- 响应 `data.source.id` 等于请求来源，例如 `garmin`。
- 响应包含 `authorization_required`、`can_start_import`、`consent_required`、`read_fields`、`save_location`、`revocation`、`privacy_boundary`、`failure_handling`。
- `read_fields` 只列出导入必须读取的活动字段，不出现第三方账号密码、原始 token 或无关隐私字段。

失败示例：
- `source=garmin` 返回 500 或缺少 `privacy_boundary`。
- `read_fields` 中出现 `password`、`api_key`、`raw_token`。
- 未登录用户也能读取预检结果。

建议验证：
- 运行 `pytest tests/test_running_data_import_precheck.py`。
- 人工抽查 `backend/routes/running_data_imports.py` 中 `running_data_import_precheck` 返回字段。

### 2. 启动导入必须依赖显式授权确认

检查对象：`POST /api/v1/running-data-imports/start`。

通过标准：
- `consent_acknowledged=false` 时返回 403。
- `consent_acknowledged=true` 且来源合法时返回 202。
- 当前占位实现必须明确 `import_started=false`，避免误导前端或用户认为后台已真正导入。
- 未登录请求返回 401。

失败示例：
- 未勾选授权确认仍返回 202。
- 返回 `import_started=true`，但后端没有真实导入任务。
- 错误提示不是稳定字段，前端无法判断下一步。

建议验证：
- 运行 `pytest tests/test_running_data_import_precheck.py -k start`。
- 抽查移动端按钮是否只有在预检确认后才允许发起 start 请求。

### 3. 来源枚举和错误码一致

检查对象：`source` 参数和请求体中的来源字段。

通过标准：
- 支持来源清单至少覆盖 `coros`、`garmin`、`generic`、`manual_file`。
- 不支持来源返回 422，错误信息包含允许值，便于前端提示用户选择正确平台。
- `precheck`、`start`、`wizard` 三个入口对非法来源行为一致。

失败示例：
- `precheck` 对非法来源返回 422，但 `wizard` 返回 500。
- 错误信息只写 `invalid source`，没有允许值，前端无法展示可选平台。
- 新增来源只改了前端下拉框，后端 `SUPPORTED_SOURCES` 未同步。

建议验证：
- 运行 `pytest tests/test_running_data_import_precheck.py -k unsupported`。
- 新增来源时同时更新后端来源枚举、测试样例和移动端来源文案。

### 4. CSV/JSON 字段识别契约稳定

检查对象：`POST /api/v1/running-data-imports/wizard`。

通过标准：
- CSV 输入能识别中文表头，例如 `活动名称`、`开始时间`、`距离(km)`。
- JSON 输入能识别常见英文键，例如 `name`、`startTime`、`distance`、`duration`。
- 响应包含 `field_mapping`、`missing_fields`、`preview`、`errors`、`duplicate_count`。
- 预览行保留 `row_number`、`title`、`start_time`、`distance_km`、`duration_seconds`、`location`、`duplicate`、`duplicate_reason`。

失败示例：
- CSV 有中文表头但 `field_mapping.title` 为空。
- JSON 数组只解析第一条或直接报 500。
- 响应字段改名导致移动端仍读取旧字段而空白。

建议验证：
- 运行 `pytest tests/test_running_data_import_wizard.py -k previews`。
- 变更 `FIELD_ALIASES` 时补充至少一个 CSV 和一个 JSON 测试样例。

### 5. 缺失字段必须可解释

检查对象：向导对缺少字段的导入样例处理。

通过标准：
- 缺少标准字段时，`missing_fields` 列出标准字段名，例如 `duration_seconds`。
- 行级缺少 `title` 或 `start_time` 时，`errors` 包含 `row`、`fields`、`message`。
- 错误信息应使用中文，且能让用户知道需要补齐哪些数据。

失败示例：
- 缺少时只返回 500。
- `errors` 只有字符串，没有行号，移动端无法定位问题行。
- 提示文案为英文 `required field missing`，不符合中文用户场景。

建议验证：
- 构造缺少 `活动名称` 或 `开始时间` 的 CSV，确认 `errors` 有行号和中文 message。
- 对照 `backend/import_error_copy.py` 的「缺少字段」规则。

### 6. 重复活动识别可靠

检查对象：导入预览中的重复活动标识。

通过标准：
- 已存在活动按「活动名称 + 开始时间精确到分钟」识别重复。
- 重复行 `duplicate=true`，`duplicate_reason=活动已存在`。
- `duplicate_count` 等于预览中重复行数量。
- 重复活动只在预览阶段标记，不应在向导阶段写入新活动。

失败示例：
- 同名同分钟活动未标记重复。
- 只按标题去重，导致不同日期的同名训练被误判。
- `duplicate_count=1` 但预览行没有任何 `duplicate=true`。

建议验证：
- 运行 `pytest tests/test_running_data_import_wizard.py -k duplicates`。
- 新增真实导入写入逻辑前，补充「重复跳过/覆盖/合并」的显式测试。

### 7. 中文错误提示一致

检查对象：接口错误信息和统一文案规则。

通过标准：
- JSON 解析失败返回 `无法解析 JSON 内容`。
- CSV 表头解析失败返回 `无法解析 CSV 表头`。
- 重复活动提示统一为 `活动已存在` 或规则表推荐文案。
- 文案检查器规则覆盖缺少字段、格式错误、重复活动、权限不足、来源平台不支持。

失败示例：
- 同一场景在接口、CLI、移动端分别显示三套文案。
- 用户看到英文栈信息或 `ValueError` 原文。
- 文案只说「失败」，没有下一步建议。

建议验证：
- 运行 `pytest tests/test_running_data_import_error_copy.py`。
- 运行 `python scripts/check_import_error_copy.py`（若脚本维护了当前样本）。

### 8. 移动端展示联动不破坏

检查对象：移动端或前端导入页对预检与向导响应的消费方式。

通过标准：
- 预检页展示来源名称、读取字段、保存位置、撤销授权入口、失败处理说明。
- 向导页展示字段映射、缺失字段、前 20 行预览、重复活动数量和行级错误。
- 前端不得依赖后端未承诺字段；如新增字段必须保持旧字段兼容。
- 移动端对 401、403、422、400 分别展示可行动中文提示。

失败示例：
- 后端把 `input_format` 改为 `format`，移动端预览页空白。
- 403 被统一展示为「服务器错误」，用户不知道要确认授权。
- 重复活动只在后端返回，移动端没有任何标识。

建议验证：
- 真实或模拟请求 `precheck`、`start`、`wizard` 后，确认移动端字段绑定仍命中。
- 如当前项目缺少前端导入页，应在风险点中记录并补齐契约测试或 mock 页面。

### 9. 安全红线检查

检查对象：导入接口、配置和测试样例。

通过标准：
- 项目中不出现硬编码真实密钥，例如 `password` 变量直接赋字符串、`api_key` 变量直接赋字符串、`token` 变量直接赋字符串。
- 预检响应不返回第三方账号密码或原始授权 token。
- 导入内容解析不拼接 SQL，不直接执行用户上传内容。
- 错误响应不泄露服务器路径、栈信息或数据库异常细节。

失败示例：
- 在代码中写入真实的第三方服务密钥或长期有效令牌。
- JSON 解析失败时把完整 traceback 返回给用户。
- 用字符串拼接把 CSV 字段拼进 SQL 查询。

建议验证：
- 运行 `grep -RInE 'password\s*=\s*"|api_key\s*=\s*"|token\s*=\s*"' backend tests scripts docs`，测试 fixture 中的假密码需要人工确认不是密钥泄露。
- 抽查 `running_data_imports.py` 中是否存在原始 SQL 拼接。

### 10. 回归测试范围明确

检查对象：跑步数据导入相关自动化测试。

通过标准：
- 至少运行 `tests/test_running_data_import_precheck.py`、`tests/test_running_data_import_wizard.py`、`tests/test_running_data_import_error_copy.py`。
- 若修改路由注册，运行 `tests/test_app_route_registration.py`。
- 若修改活动去重依赖，补跑 `tests` 中活动创建和活动列表相关用例。
- 全量发布前应运行 `pytest`，不得放过失败测试。

失败示例：
- 只手工点了一个成功路径，没有覆盖非法来源、缺少授权、坏 JSON、重复活动。
- 相关测试 xfail 或 skip，但没有明确原因和补齐任务。
- 测试失败仍把实现任务标记 done。

建议验证：
- 开发阶段轻量运行：`pytest tests/test_running_data_import_precheck.py tests/test_running_data_import_wizard.py tests/test_running_data_import_error_copy.py`。
- 发布前运行：`pytest`。

## 二、当前项目最需要补齐的 3 个风险点

### 风险点 1：移动端导入展示联动缺少可见实现或测试

当前观察：后端已有 `precheck`、`start`、`wizard` 接口与测试，但在当前文件树中未发现明确的移动端导入向导页面或前端字段绑定测试。

影响：后端契约即使通过，移动端仍可能无法展示授权范围、缺失字段、重复活动和行级错误。

建议补齐：
- 增加移动端/前端导入向导 mock 或组件测试。
- 固化字段绑定：`authorization_required`、`read_fields`、`field_mapping`、`missing_fields`、`preview`、`duplicate_count`。
- 对 400、401、403、422 分别建立中文提示断言。

### 风险点 2：错误文案规则与实际接口文案存在分层，需要持续同步

当前观察：项目有 `backend/import_error_copy.py` 统一规则，但接口中仍直接返回 `无法解析 JSON 内容`、`无法解析 CSV 表头`、`source must be one of...` 等具体文案。

影响：后续新增场景时，接口文案、规则表和移动端提示可能漂移，导致用户看到不一致提示。

建议补齐：
- 将接口实际错误样本纳入 `tests/test_running_data_import_error_copy.py` 或脚本样本。
- 变更文案时同时更新规则表、接口测试和移动端提示快照。
- 对英文技术错误保留内部日志，外部响应统一中文可行动提示。

### 风险点 3：真实导入写入尚未闭环，重复处理策略需要提前锁定

当前观察：`start` 当前返回 `authorized_precheck_only` 且 `import_started=false`，向导只做预览和重复标记。

影响：后续加入真实写入时，最容易出现重复活动误写入、部分失败写入不一致、回滚策略不清晰等问题。

建议补齐：
- 在真实导入任务开工前定义重复策略：跳过、覆盖、合并或由用户逐条确认。
- 增加事务/回滚测试：一批中部分坏行失败时不得写入未确认活动。
- 增加幂等测试：同一导入请求重复提交不得创建重复活动。

## 三、QA Gate 执行顺序建议

1. 查制品：确认相关实现或文档路径存在且超过 10 行。
2. 跑导入专项测试：`pytest tests/test_running_data_import_precheck.py tests/test_running_data_import_wizard.py tests/test_running_data_import_error_copy.py`。
3. 跑路由注册测试：`pytest tests/test_app_route_registration.py`。
4. 做安全 grep：检查硬编码密钥、原始 token、SQL 拼接和 traceback 泄露。
5. 做 import 检查：`python -c "import backend; import backend.routes.running_data_imports; import backend.import_error_copy"`。
6. 若移动端入口已存在，补充一次字段绑定或接口 mock 检查。
7. 任何一步失败，都创建具体修复任务，指明失败命令、文件路径和推荐 assignee。

## 四、最小通过门槛

开发任务标记 done 前，至少应满足：
- 跑步数据导入专项 pytest 全绿。
- `backend` 和相关导入模块可 import，无语法错误。
- 无硬编码真实密钥或敏感 token 泄露。
- 向导响应字段与移动端约定一致，若移动端尚未实现，必须在任务 handoff 中说明缺口。
- 重复活动、缺少字段、非法来源、未授权和坏 JSON 至少各有一个自动化断言或明确的后续修复任务。
