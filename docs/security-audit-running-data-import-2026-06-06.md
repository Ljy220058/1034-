# 安全审计报告

审计对象：1034 跑团管理系统跑步数据导入流程（高驰、佳明、CSV/JSON/手动文件导入）
审计范围：后端接口、前端入口、数据模型、认证授权、输入验证、SQL、密钥配置
审计日期：2026-06-06

## 已梳理入口

- 后端接口：`backend/routes/running_data_imports.py:206` `GET /api/v1/running-data-imports/precheck`
- 后端接口：`backend/routes/running_data_imports.py:228` `POST /api/v1/running-data-imports/start`
- 后端接口：`backend/routes/running_data_imports.py:247` `POST /api/v1/running-data-imports/wizard`
- 后端接口：`backend/routes/running_data_imports.py:269` `POST /api/v1/running-data-imports/anomaly-precheck`
- 数据解析：`backend/routes/running_data_imports.py:96` CSV 解析、`backend/routes/running_data_imports.py:108` JSON 解析
- 异常预检：`backend/running_data_anomaly_precheck.py:122` 跑步数据异常预检
- 活动模型：`backend/models.py:58` `ActivityBase`、`backend/models.py:71` `ActivityCreate`
- 活动存储：`backend/database.py:30` `activities` 表、`backend/activity_registration_risk.py:85` 全量活动列表
- 前端入口：`frontend/index.html` 未发现 `running-data-imports`、高驰、佳明、导入向导或异常预检的字段绑定；`docs/running_data_import_wizard_smoke_checklist.md:28` 已记录“当前未发现明确导入向导页面或字段绑定实现”。

## 严重 (CVSS >= 7)

### [backend/routes/common.py:53] 认证 token 未签名，可伪造访问跑步导入接口 (CVSS: 8.1)
- 攻击向量：攻击者读取代码后得知 token 格式为 `member.id:member.role:expires_at`，构造任意未来过期时间的 Bearer token；`parse_token` 只解析字段并检查成员存在和角色相同，没有验证签名、issuer、audience、jti 或撤销状态。攻击者枚举已有成员 id 后，以该成员身份调用 `/api/v1/running-data-imports/wizard`、`/anomaly-precheck` 和活动相关接口。
- 影响：跑步导入预览、重复活动判断、异常预检与成员权限边界被绕过；被冒充成员的数据访问、导入授权状态和后续真实导入动作全部失去可信身份保证。
- 修复：使用服务端密钥签名 JWT，并强制校验 `exp`、`sub`、`role`、`iss`、`aud`；密钥只来自环境变量。
```python
# backend/routes/common.py
import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, status

JWT_SECRET = os.environ["RUNNING_CLUB_JWT_SECRET"]
JWT_ALG = "HS256"
JWT_ISSUER = "1034-running-club"
JWT_AUDIENCE = "1034-api"
TOKEN_TTL_HOURS = 7

def token_for_member(member: Any) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(member.id),
        "role": member.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def parse_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALG],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require_exp": True, "require_sub": True},
        )
        member_id = int(payload["sub"])
        role = str(payload["role"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token") from exc

    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/auth.py:19] 密码使用无盐 SHA-256 存储，数据库泄露后可离线撞库 (CVSS: 7.5)
- 攻击向量：攻击者获得 SQLite 数据库或备份后，直接对 `members.password_hash` 中的 SHA-256 值进行字典攻击；注册和登录路径均使用 `hashlib.sha256(password)`，没有 Argon2id/bcrypt、盐值、pepper 或工作因子。
- 影响：成员账号、管理员账号和导入授权入口被接管；被接管账号可读取跑步导入预检结果、活动列表和后续真实导入能力。
- 修复：使用 Argon2id 或 bcrypt 存储密码哈希；登录时兼容旧哈希并在成功登录后升级。
```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    return pwd_context.verify(password, stored_hash)

@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> ApiResponse:
    password_hash = hash_password(payload.password)
    member, outcome = create_member_with_password(sanitize_member_payload(payload), password_hash)
    if outcome == 'conflict' or member is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='phone already registered')
    return ApiResponse(data={'token_type': 'Bearer', 'access_token': token_for_member(member), 'member': member_to_public(member)})

@router.post('/login', response_model=ApiResponse)
def login(payload: UserLogin) -> ApiResponse:
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE phone = ?', (payload.phone,)).fetchone()
    if row is None or not row['password_hash'] or not verify_password(payload.password, row['password_hash']):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    member = get_member(row['id'])
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    return ApiResponse(data={'token_type': 'Bearer', 'access_token': token_for_member(member), 'member': member_to_public(member)})
```

### [backend/routes/running_data_imports.py:163] 导入向导用全量活动做重复检测，成员可探测他人跑步记录 (CVSS: 7.1)
- 攻击向量：任意已登录成员向 `/api/v1/running-data-imports/wizard` 提交猜测的活动标题和开始时间；`_existing_activity_keys()` 调用 `list_activities()` 读取全站活动，再在 `duplicate_reason='活动已存在'` 中返回匹配结果。攻击者批量提交候选标题和时间，即可确认其他成员或全站已有活动记录。
- 影响：跑步标题、开始时间和活动存在性被越权读取；这些字段可暴露个人运动规律、居住/训练时间段和社交活动轨迹。
- 修复：活动和导入预览必须按当前用户或可见范围过滤；重复检测只比较当前用户拥有或有权限读取的活动。
```python
# backend/routes/running_data_imports.py
from ..repository import list_activities_for_member

def _existing_activity_keys(current_user: CurrentUser) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for activity in list_activities_for_member(current_user.id):
        data = activity.model_dump(mode='json') if hasattr(activity, 'model_dump') else dict(activity)
        title = str(data.get('title') or '').strip()
        start_time = str(data.get('start_time') or '').strip()
        if title and start_time:
            keys.add((title, start_time[:16]))
    return keys

def _build_preview(rows: list[dict[str, Any]], mapping: dict[str, str], current_user: CurrentUser) -> tuple[list[ImportPreviewRow], list[dict[str, Any]]]:
    existing_keys = _existing_activity_keys(current_user)
    # 保持后续逻辑不变

@router.post('/wizard', response_model=ApiResponse)
def running_data_import_wizard(payload: ImportWizardRequest, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    rows, headers = _parse_csv(payload.content) if payload.format == 'csv' else _parse_json(payload.content)
    mapping = _detect_mapping(headers)
    preview, errors = _build_preview(rows, mapping, current_user)
    return ApiResponse(data=ImportWizardResult(...).model_dump(mode='json'), message='识别完成')
```

## 中等 (CVSS 4-6)

### [backend/routes/running_data_imports.py:61] 导入内容只限制字节长度，不限制行数和字段敏感性 (CVSS: 6.5)
- 攻击向量：攻击者上传 200KB 内的高行数 CSV/JSON，触发 `_parse_csv()`、`_parse_json()`、`_build_preview()` 和异常预检对全部行处理；同时可夹带 `access_token`、`refresh_token`、`password`、`api_key` 等字段，服务端会解析表头并返回字段映射、错误行号和异常统计。
- 影响：接口 CPU/内存被消耗；第三方平台 token、GPS 轨迹和账号字段进入请求日志、错误跟踪或后续调试链路，破坏“token 不保存”和最小化采集边界。
- 修复：添加最大行数、最大字段数、敏感字段拒绝和 GPS/令牌脱敏；解析阶段超过限制立即返回 413/422。
```python
# backend/routes/running_data_imports.py
MAX_IMPORT_ROWS = 200
MAX_IMPORT_COLUMNS = 40
SENSITIVE_HEADERS = {'password', 'passwd', 'secret', 'token', 'access_token', 'refresh_token', 'api_key', 'authorization'}

def _reject_sensitive_headers(headers: list[str]) -> None:
    lowered = {header.strip().lower() for header in headers}
    blocked = sorted(lowered & SENSITIVE_HEADERS)
    if blocked:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='导入文件包含敏感字段，已拒绝处理')
    if len(headers) > MAX_IMPORT_COLUMNS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入字段数量超过限制')

def _enforce_row_limit(rows: list[dict[str, Any]]) -> None:
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='导入行数超过限制')

def _parse_csv(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    reader = csv.DictReader(StringIO(content))
    headers = [header.strip() for header in (reader.fieldnames or []) if header and header.strip()]
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法解析 CSV 表头')
    _reject_sensitive_headers(headers)
    rows = [{str(key).strip(): value for key, value in row.items() if key is not None} for row in reader]
    _enforce_row_limit(rows)
    return rows, headers
```

### [backend/routes/running_data_imports.py:228] 授权确认只信任客户端布尔值，缺少服务端同意记录和撤销校验 (CVSS: 5.9)
- 攻击向量：攻击者拿到任意有效 Bearer token 后，直接向 `/api/v1/running-data-imports/start` 发送 `{"source":"garmin","consent_acknowledged":true}`；服务端没有保存用户、来源、授权字段、同意版本、过期时间和撤销状态，后续真实导入实现无法证明授权来自本人确认。
- 影响：高驰/佳明导入授权审计链缺失；用户撤销授权后，后台任务和后续导入实现缺少强制拒绝依据。
- 修复：增加 `running_import_consents` 表；`/start` 写入同意记录，真实导入和异常预检读取服务端 consent 状态，撤销接口更新 `revoked_at`。
```python
# backend/database.py
CREATE TABLE IF NOT EXISTS running_import_consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('coros', 'garmin', 'generic', 'manual_file')),
    read_fields TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    granted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    UNIQUE(member_id, source),
    FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
);

# backend/routes/running_data_imports.py
CONSENT_VERSION = 'running-import-v1'

def _grant_import_consent(member_id: int, source: str) -> None:
    read_fields = json.dumps(['activity_id', 'started_at', 'duration_seconds', 'distance_meters', 'pace_seconds_per_km', 'heart_rate_summary', 'gps_track_summary'])
    with connect() as connection:
        connection.execute(
            '''
            INSERT INTO running_import_consents (member_id, source, read_fields, consent_version, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(member_id, source) DO UPDATE SET
                read_fields = excluded.read_fields,
                consent_version = excluded.consent_version,
                granted_at = CURRENT_TIMESTAMP,
                revoked_at = NULL
            ''',
            (member_id, source, read_fields, CONSENT_VERSION),
        )

@router.post('/start', response_model=ApiResponse, status_code=status.HTTP_202_ACCEPTED)
def start_running_data_import(payload: ImportStartRequest, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    if payload.source not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='source must be one of: coros, garmin, generic, manual_file')
    if not payload.consent_acknowledged:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='running data import requires explicit consent precheck acknowledgement')
    _grant_import_consent(current_user.id, payload.source)
    return ApiResponse(data={'status': 'consent_recorded', 'source': _source_payload(payload.source), 'import_started': False}, message='已确认授权')
```

### [backend/models.py:58] 活动模型允许额外字段，真实导入扩展时会形成隐私字段落库缺口 (CVSS: 5.3)
- 攻击向量：导入数据包含 `gps_track`、`heart_rate_summary`、`access_token` 等额外字段；`ActivityBase` 和 `ActivityCreate` 设置 `model_config = {'extra': 'allow'}`。当前 `create_activity()` 只插入白名单列，但后续真实导入复用 `model_dump()`、JSON 元数据列或批量 upsert 时，额外字段会绕过 schema 设计进入数据库或响应。
- 影响：GPS 轨迹、心率摘要和第三方平台字段超出预检中声明的 `gps_track_summary` 边界，破坏数据最小化原则。
- 修复：活动创建模型禁止额外字段；真实导入单独定义白名单 schema，并在落库前显式脱敏 GPS 和心率字段。
```python
# backend/models.py
from pydantic import ConfigDict

class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    max_participants: Optional[int] = Field(default=None, gt=0)
    model_config = ConfigDict(extra='forbid')

class RunningImportActivity(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    distance_km: float = Field(ge=0, le=100)
    duration_seconds: int = Field(gt=0, le=86400)
    gps_track_summary: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra='forbid')
```

## 低危 (CVSS < 4)

### [.gitignore:1] 未忽略 `.env`，密钥文件存在误提交风险 (CVSS: 3.1)
- 攻击向量：开发者把 `RUNNING_CLUB_JWT_SECRET`、第三方导入 client secret 或数据库路径写入 `.env` 后，当前 `.gitignore` 未匹配 `.env`、`.env.*`，密钥文件可被提交到仓库。
- 影响：JWT 签名密钥、导入平台凭证和本地数据库路径泄露；攻击者可伪造 token 或接管第三方导入集成。
- 修复：忽略环境文件并提交 `.env.example`。
```gitignore
# Environment / secrets
.env
.env.*
!.env.example
```

### [frontend/index.html:1] 前端缺少导入向导入口，隐私授权说明无法在用户操作前强制展示 (CVSS: 3.0)
- 攻击向量：用户或移动端集成方绕过 UI，直接调用 `/start` 或 `/wizard`；前端未绑定 `authorization_required`、`read_fields`、`privacy_boundary`、`revocation` 等字段，授权范围无法在操作前强制呈现。
- 影响：用户对高驰/佳明读取字段、撤销入口、GPS 数据边界和失败处理缺少明确确认，形成合规和审计缺口。
- 修复：新增导入向导页面，先调用 `/precheck` 展示隐私边界，用户勾选确认后才允许调用 `/start` 或 `/wizard`。
```javascript
async function openRunningImport(source) {
  const precheck = await apiGet(`/api/v1/running-data-imports/precheck?source=${encodeURIComponent(source)}`);
  renderPrivacyPanel(precheck.data.read_fields, precheck.data.privacy_boundary, precheck.data.revocation);
  confirmButton.disabled = true;
  consentCheckbox.addEventListener('change', () => {
    confirmButton.disabled = !consentCheckbox.checked;
  });
}

async function confirmRunningImport(source) {
  if (!consentCheckbox.checked) return;
  await apiPost('/api/v1/running-data-imports/start', {
    source,
    consent_acknowledged: true,
  });
}
```

## OWASP Top 10 覆盖

- A01 Broken Access Control：发现全量活动重复检测导致越权探测，见 `backend/routes/running_data_imports.py:163`。
- A02 Cryptographic Failures：发现未签名 token、SHA-256 密码哈希、`.env` 未忽略。
- A03 Injection：活动、成员、导入相关 SQL 使用参数化查询；`activity_registration_risk.py:116` 的动态 UPDATE 字段来自固定白名单，未发现可控 SQL 注入点。
- A04 Insecure Design：发现 consent 只信任客户端布尔值，缺少服务端授权记录和撤销校验。
- A05 Security Misconfiguration：发现 `.env` 未忽略；健康检查暴露数据库路径的风险需在生产环境限制访问。
- A06 Vulnerable and Outdated Components：本次静态范围未发现依赖锁文件中与导入直接相关的版本证据；建议在 CI 增加 `uv pip audit` 或 `pip-audit`。
- A07 Identification and Authentication Failures：发现未签名 token 与弱密码哈希。
- A08 Software and Data Integrity Failures：导入内容未限制行数和敏感字段，真实导入前缺少文件完整性/格式白名单门禁。
- A09 Security Logging and Monitoring Failures：授权确认、撤销和真实导入缺少可审计 consent 记录。
- A10 SSRF：当前导入实现不访问高驰/佳明外部 URL，不存在 SSRF 触发点；后续接入第三方 API 时禁止用户提供任意 URL。

## 密钥/配置检查

- [ ] JWT secret 是否在环境变量中：未通过。当前 `backend/routes/common.py:53` 未使用 JWT secret，token 未签名。
- [x] 数据库连接串是否含明文密码：通过。SQLite 路径来自 `RUNNING_CLUB_DB_PATH` 或临时目录，未包含数据库密码。
- [ ] `.env` 是否在 `.gitignore`：未通过。`.gitignore:1-15` 未包含 `.env` 或 `.env.*`。
- [ ] 第三方高驰/佳明 token 是否明文保存：当前未实现真实第三方 token 持久化；后续实现必须使用加密列或外部 secrets manager，不得把 access token/refresh token 写入普通 TEXT 列。

## 验证

- 静态热点搜索：搜索 `password|secret|token|api_key|execute(`、`UploadFile|File|Form|fit|gpx|tcx|csv|coros|garmin|高驰|佳明`，定位到认证、导入路由、活动模型和配置风险。
- 逐文件审计：`backend/routes/running_data_imports.py`、`backend/running_data_anomaly_precheck.py`、`backend/routes/common.py`、`backend/routes/auth.py`、`backend/models.py`、`backend/database.py`、`backend/activity_registration_risk.py`、`frontend/index.html`、`.gitignore`。
- 测试命令：`uv run pytest -q tests/test_running_data_import_regression.py tests/test_running_data_import_anomaly_precheck.py tests/test_running_data_import_smoke_checklist.py tests/test_route_registration.py`
- 测试结果：18 passed, 4 warnings in 0.64s。
- Git 历史命令：`git log --oneline --decorate -n 12 -- backend/routes/running_data_imports.py backend/running_data_anomaly_precheck.py backend/routes/common.py`
- Git 历史结果：`74edc17 feat: full project — backend API, frontend UI, docs, tests, CI/CD`。
