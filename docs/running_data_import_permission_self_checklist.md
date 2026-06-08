# 跑步数据导入权限自检清单

适用范围：1034 跑团管理系统跑步数据导入流程，覆盖佳明、高驰、手动 CSV/JSON 文件导入三类入口。本文只记录权限与隐私自检项，不发起真实第三方连接，不保存第三方账号密码或原始授权 token。

## 一、审计结论摘要

当前后端已提供 `GET /api/v1/running-data-imports/precheck`、`POST /api/v1/running-data-imports/start`、`POST /api/v1/running-data-imports/wizard`、`POST /api/v1/running-data-imports/anomaly-precheck` 四个导入相关入口，并且都依赖 `get_current_user` 登录态。现有实现仍存在 4 个权限自检缺口：第三方授权状态未绑定到用户、向导/异常预检未强制授权确认、导入预检读取字段缺少按来源分级、前端/移动端导入入口缺少可见字段绑定与错误码分支测试。

攻击者视角：已登录普通成员可直接调用向导和异常预检接口处理任意上传内容；后续接入真实佳明/高驰 OAuth 或 Cookie 导入后，如果沿用当前占位契约，攻击者可绕过“先看授权范围再确认”的流程，诱导系统处理超范围数据或把错误响应暴露给非预期调用方。

## 二、现有入口与权限校验现状

| 入口 | 当前实现位置 | 当前权限校验 | 当前缺口 |
| --- | --- | --- | --- |
| 佳明预检 | `backend/routes/running_data_imports.py:206` | 必须登录；校验 `source in SUPPORTED_SOURCES` | 只返回通用读取字段，未区分佳明真实授权 scope、授权状态、过期时间、撤销状态。 |
| 高驰预检 | `backend/routes/running_data_imports.py:206` | 必须登录；校验 `source in SUPPORTED_SOURCES` | 只返回通用读取字段，未区分高驰真实授权 scope、授权状态、过期时间、撤销状态。 |
| 导入启动 | `backend/routes/running_data_imports.py:228` | 必须登录；`consent_acknowledged=false` 返回 403 | 只信任请求体布尔值，没有服务端授权记录；后续真实导入必须绑定 `current_user.id + source + consent_version`。 |
| CSV/JSON 向导 | `backend/routes/running_data_imports.py:247` | 必须登录；校验来源、格式、内容大小 | 不要求先完成预检确认；任何已登录用户可直接提交最多 200KB 内容做解析和重复检查。 |
| 异常预检 | `backend/routes/running_data_imports.py:269` | 必须登录；校验来源、格式、内容大小 | 不要求先完成预检确认；响应内包含 `sample_request` 和字段映射，后续若加入真实导入上下文需避免泄露授权细节。 |
| 前端/移动端入口 | `frontend/index.html`、`frontend/*.js` | 当前文件树未发现明确导入向导页面或字段绑定逻辑 | 缺少 400/401/403/422 中文提示、授权范围展示、字段绑定、重复活动标识的可见验收入口。 |
| 中文文案规则 | `backend/import_error_copy.py:71` | 有规则表覆盖缺少字段、格式错误、重复活动、权限不足、来源平台不支持 | 接口实际文案仍有英文技术字符串，例如 `source must be one of...`、`running data import requires explicit consent precheck acknowledgement`。 |

## 三、权限自检清单

### CHECK-01 佳明授权记录必须绑定当前用户

- 检查项：佳明真实接入前，服务端必须保存并校验 `current_user.id`、`source=garmin`、授权版本、授权状态、过期时间、撤销时间，不得只依赖前端传入 `source` 或 `consent_acknowledged`。
- 风险：攻击者使用自己的登录态直接调用 `/start` 或后续真实导入接口，绕过“谁授权、授权了什么、是否撤销”的服务端判断，触发超范围读取或跨用户导入。
- 攻击向量：已登录成员构造 `source=garmin&consent_acknowledged=true` 请求，绕过前端预检页面，利用后续真实导入任务读取未绑定到该成员的第三方授权上下文。
- 建议实现位置：`backend/routes/running_data_imports.py:228`；新增服务层 `backend/running_data_import_authorizations.py`；新增表迁移 `running_data_import_authorizations`。
- 修复示例：

```python
@dataclass(frozen=True)
class ImportAuthorization:
    user_id: int
    source: str
    scopes: tuple[str, ...]
    consent_version: str
    expires_at: datetime
    revoked_at: datetime | None = None


def require_import_authorization(user_id: int, source: str, required_scopes: set[str]) -> ImportAuthorization:
    authorization = get_latest_import_authorization(user_id=user_id, source=source)
    if authorization is None or authorization.revoked_at is not None:
        raise HTTPException(status_code=403, detail='请先确认导入授权范围后再继续')
    if authorization.expires_at < utcnow():
        raise HTTPException(status_code=403, detail='导入授权已过期，请重新确认授权范围')
    if not required_scopes.issubset(set(authorization.scopes)):
        raise HTTPException(status_code=403, detail='导入授权范围不足，请重新授权')
    return authorization
```

- 验收方式：新增测试 `tests/test_running_data_import_authorization.py`，断言无授权、授权过期、授权撤销、scope 缺失均返回 403；不同用户不能复用同一授权记录。

### CHECK-02 高驰授权 scope 与最小化读取字段必须独立配置

- 检查项：高驰入口必须独立列出并校验最小读取字段，只允许活动 ID、开始时间、距离、时长、配速摘要、心率摘要、GPS 轨迹摘要，不读取账号密码、原始 token、联系人、设备序列号和完整位置轨迹明细。
- 风险：当前 `read_fields` 在 `backend/routes/running_data_imports.py:218` 对全部来源返回同一清单。后续新增高驰真实接入时，开发者会复用通用字段，导致高驰授权页展示与实际读取范围不一致。
- 攻击向量：攻击者诱导用户授权“导入跑步记录”，服务端实际读取超出展示范围的字段；一旦日志或错误响应记录这些字段，敏感运动轨迹和设备信息外泄。
- 建议实现位置：`backend/routes/running_data_imports.py:18`、`backend/routes/running_data_imports.py:218`；把 `SUPPORTED_SOURCES` 扩展为包含 `required_scopes`、`read_fields`、`forbidden_fields`。
- 修复示例：

```python
SUPPORTED_SOURCES = {
    'coros': {
        'id': 'coros',
        'name': '高驰',
        'required_scopes': ['activity.read'],
        'read_fields': ['activity_id', 'started_at', 'duration_seconds', 'distance_meters', 'pace_seconds_per_km', 'heart_rate_summary', 'gps_track_summary'],
        'forbidden_fields': ['password', 'raw_token', 'device_serial', 'contacts', 'full_gps_track'],
    },
    'garmin': {
        'id': 'garmin',
        'name': '佳明',
        'required_scopes': ['activity.read'],
        'read_fields': ['activity_id', 'started_at', 'duration_seconds', 'distance_meters', 'pace_seconds_per_km', 'heart_rate_summary', 'gps_track_summary'],
        'forbidden_fields': ['password', 'raw_token', 'device_serial', 'contacts', 'full_gps_track'],
    },
}


def _source_payload(source: str) -> dict[str, object]:
    config = SUPPORTED_SOURCES[source]
    return {
        'id': config['id'],
        'name': config['name'],
        'required_scopes': config['required_scopes'],
        'read_fields': config['read_fields'],
    }
```

- 验收方式：新增断言 `source=coros` 与 `source=garmin` 的响应均包含 `required_scopes`；`read_fields` 不包含 `password`、`token`、`raw_token`、`device_serial`、`contacts`、`full_gps_track`。

### CHECK-03 手动 CSV/JSON 向导必须要求用户先确认本地文件隐私边界

- 检查项：`POST /api/v1/running-data-imports/wizard` 和 `/anomaly-precheck` 在处理 `manual_file`、`generic` 内容前，必须要求服务端存在最近一次预检确认记录，确认用户知道文件会被解析但不会在向导阶段落库。
- 风险：当前向导只依赖登录态和请求体校验，未强制“预检 → 授权确认 → 解析预览”的顺序。攻击者可通过钓鱼页面诱导已登录用户上传包含完整 GPS、备注、设备信息的 CSV/JSON 到接口。
- 攻击向量：攻击者让用户在第三方页面粘贴导出的运动数据，再由页面代发到 `/wizard`；接口返回预览、重复检查和异常信息，绕过系统自带隐私提示。
- 建议实现位置：`backend/routes/running_data_imports.py:247`、`backend/routes/running_data_imports.py:269`；复用 CHECK-01 的授权确认记录，但 `source in {'generic', 'manual_file'}` 使用 `local_file.preview` scope。
- 修复示例：

```python
@router.post('/wizard', response_model=ApiResponse)
def running_data_import_wizard(payload: ImportWizardRequest, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    if payload.source not in SUPPORTED_SOURCES:
        raise_unsupported_source()
    require_import_authorization(
        user_id=current_user.id,
        source=payload.source,
        required_scopes={'local_file.preview'} if payload.source in {'generic', 'manual_file'} else {'activity.read'},
    )
    rows, headers = _parse_csv(payload.content) if payload.format == 'csv' else _parse_json(payload.content)
    ...
```

- 验收方式：新增测试：未确认预检直接调用 `/wizard` 与 `/anomaly-precheck` 返回 403；确认后返回 200；向导阶段活动数量不增加。

### CHECK-04 导入失败提示必须统一中文且可行动

- 检查项：所有导入入口对 400、401、403、422 返回中文提示；不得向用户暴露英文内部字符串、Python 异常类名、数据库错误、文件路径。
- 风险：`backend/import_error_copy.py:71` 已定义统一中文规则，但接口实际返回仍包含 `source must be one of...` 和 `running data import requires explicit consent precheck acknowledgement`，前端无法稳定映射为中文可行动提示。
- 攻击向量：攻击者批量提交非法来源或坏 JSON，利用错误差异枚举后端实现细节；用户端显示英文技术错误，降低对授权失败和格式失败的理解，诱导重复上传敏感文件。
- 建议实现位置：`backend/routes/running_data_imports.py:209`、`backend/routes/running_data_imports.py:231`、`backend/routes/running_data_imports.py:250`、`backend/routes/running_data_imports.py:272`、`backend/import_error_copy.py:71`。
- 修复示例：

```python
def raise_unsupported_source() -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail='暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON',
    )


def raise_missing_import_consent() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='请先确认导入授权范围后再继续',
    )
```

- 验收方式：扩展 `tests/test_running_data_import_precheck.py` 和 `tests/test_running_data_import_regression.py`，断言非法来源、未确认授权、坏 JSON、坏 CSV、缺少 token 都返回中文；运行 `python scripts/check_import_error_copy.py` 时无不一致。

### CHECK-05 日志脱敏与响应脱敏必须覆盖导入内容

- 检查项：导入接口不得记录 `payload.content` 原文、第三方 access token、refresh token、Cookie、完整 GPS 轨迹、身份证明字段；错误日志只记录 `user_id`、`source`、行号、错误分类、脱敏摘要。
- 风险：当前路由没有显式日志，但后续接入真实导入任务或异常处理时，最容易把 CSV/JSON 原文、第三方 token 或 GPS 轨迹写进应用日志。
- 攻击向量：攻击者上传带有伪造敏感字段名的 CSV/JSON，触发解析失败；如果异常日志记录原文，日志查看者或日志聚合系统获得用户运动轨迹和第三方凭据。
- 建议实现位置：`backend/routes/running_data_imports.py` 的异常分支；新增 `backend/running_data_import_logging.py`。
- 修复示例：

```python
SENSITIVE_IMPORT_KEYS = {'password', 'token', 'access_token', 'refresh_token', 'api_key', 'cookie', 'gps_track', 'route_points'}


def redact_import_row(row: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in row.items():
        normalized = key.lower()
        if normalized in SENSITIVE_IMPORT_KEYS or 'token' in normalized or 'password' in normalized:
            redacted[key] = '[REDACTED]'
        elif normalized in {'gps_track', 'route_points', 'track'}:
            redacted[key] = '[GPS_REDACTED]'
        else:
            redacted[key] = str(value)[:80]
    return redacted
```

- 验收方式：新增单元测试覆盖 `password`、`access_token`、`refresh_token`、`api_key`、`cookie`、`gps_track` 字段脱敏；人工审查日志样例中不出现完整上传内容。

### CHECK-06 前端/移动端必须展示授权范围并按错误码分支

- 检查项：导入页必须在用户上传或启动前展示来源名称、读取字段、保存位置、撤销入口、失败处理；对 400、401、403、422 分别展示中文可行动提示。
- 风险：当前文件树中未发现明确导入向导页面或字段绑定实现，`docs/running_data_import_wizard_smoke_checklist.md:126` 已把移动端错误提示列为风险项。后端契约通过时，用户界面仍会隐藏授权范围或把权限不足显示为服务器错误。
- 攻击向量：攻击者利用 UI 缺口诱导成员直接进入上传页，用户在看不到读取字段和撤销入口的情况下提交文件；403 被展示为通用失败后，用户重复上传更完整的数据。
- 建议实现位置：`frontend/index.html`、后续导入页 JS 模块、移动端导入组件测试。
- 修复示例：

```javascript
const importErrorMessages = {
  400: '文件内容格式错误，请检查 CSV/JSON 后重试',
  401: '请先登录后再导入跑步数据',
  403: '请先确认导入授权范围后再继续',
  422: '暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON',
};

function renderPrecheck(data) {
  renderSource(data.source.name);
  renderReadFields(data.read_fields);
  renderSaveLocation(data.save_location);
  renderRevocation(data.revocation.endpoint);
  setImportButtonEnabled(data.consent_required === true && userCheckedConsent());
}
```

- 验收方式：新增前端/移动端测试，模拟 precheck、wizard 和 anomaly-precheck 响应；断言 `authorization_required`、`read_fields`、`field_mapping`、`missing_fields`、`preview`、`duplicate_count` 均有可见展示；断言 400/401/403/422 不显示“服务器错误”。

## 四、按入口执行的最小权限矩阵

| 来源入口 | 必须授权字段 | 最小化数据范围 | 失败时中文提示 | 日志脱敏要求 |
| --- | --- | --- | --- | --- |
| 佳明 `garmin` | `user_id`、`source`、`required_scopes=['activity.read']`、`consent_version`、`expires_at`、`revoked_at` | 活动 ID、开始时间、距离、时长、配速摘要、心率摘要、GPS 摘要；不读取账号密码、原始 token、设备序列号、联系人、完整轨迹 | 未登录：`请先登录后再导入跑步数据`；未授权：`请先确认导入授权范围后再继续`；授权过期：`导入授权已过期，请重新确认授权范围` | 不记录 access token、refresh token、Cookie、完整 GPS；只记录 `user_id/source/error_code/row_count`。 |
| 高驰 `coros` | `user_id`、`source`、`required_scopes=['activity.read']`、`consent_version`、`expires_at`、`revoked_at` | 活动 ID、开始时间、距离、时长、配速摘要、心率摘要、GPS 摘要；不读取账号密码、原始 token、设备序列号、联系人、完整轨迹 | 未登录：`请先登录后再导入跑步数据`；未授权：`请先确认导入授权范围后再继续`；来源不支持：`暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON` | 不记录第三方 token、Cookie、完整轨迹；失败日志不得包含第三方响应原文。 |
| 手动 CSV/JSON `generic` / `manual_file` | `user_id`、`source`、`required_scopes=['local_file.preview']`、`consent_version`、`confirmed_at` | 只解析活动名称、开始时间、距离、时长、地点、配速、GPS 摘要；向导阶段只返回前 20 行预览；真实导入前不落库 | 坏 CSV：`文件内容格式错误，请检查 CSV/JSON 后重试`；缺字段：`导入数据缺少必填字段，请补齐后重试`；重复：`活动已存在，请确认是否跳过重复记录` | 不记录上传文件原文；行级错误只记录行号、字段名、错误分类；GPS 字段写 `[GPS_REDACTED]`。 |

## 五、当前权限校验缺口清单

| 缺口 | 证据 | 风险等级 | 后续任务建议 |
| --- | --- | --- | --- |
| 服务端没有持久化导入授权记录 | `/start` 只检查 `payload.consent_acknowledged`，见 `backend/routes/running_data_imports.py:234` | 中等 | 新增导入授权表与 `require_import_authorization`，所有真实导入入口必须调用。 |
| 向导和异常预检未强制预检确认 | `/wizard` 与 `/anomaly-precheck` 只依赖登录态，见 `backend/routes/running_data_imports.py:247`、`:269` | 中等 | 给 `generic/manual_file` 增加 `local_file.preview` 确认记录校验。 |
| 佳明/高驰读取字段未按来源配置 | `read_fields` 在 `backend/routes/running_data_imports.py:218` 为通用硬编码 | 中等 | 将 `SUPPORTED_SOURCES` 扩展为来源级 scope/read_fields/forbidden_fields 配置。 |
| 中文文案规则与接口实际文案不一致 | `backend/import_error_copy.py:71` 与 `running_data_imports.py:235`、`:211` 文案不一致 | 低危 | 统一错误 helper，并把接口实际样本纳入文案检查脚本。 |
| 前端/移动端导入入口缺少可见实现 | `frontend/index.html` 和 `frontend/*.js` 未检索到 running-data-imports/garmin/coros/import 绑定 | 中等 | 创建前端导入向导或 mock 组件测试，覆盖授权范围、错误码和字段绑定。 |

## 六、验收命令

```bash
pytest -q tests/test_running_data_import_precheck.py tests/test_running_data_import_regression.py tests/test_running_data_import_anomaly_precheck.py tests/test_running_data_import_smoke_checklist.py
python -c "import backend.routes.running_data_imports; import backend.import_error_copy"
python scripts/check_import_error_copy.py
```

本次自检实际执行结果记录在 Kanban 评论中。若后续实现了真实第三方导入，还必须补充授权表迁移测试、跨用户授权隔离测试、授权撤销测试、scope 缺失测试和日志脱敏测试。
