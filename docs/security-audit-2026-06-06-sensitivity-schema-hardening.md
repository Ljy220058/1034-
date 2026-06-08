# 安全审计报告

审计对象：1034 跑团管理系统（FastAPI + SQLite）
审计范围：认证、授权、输入验证、SQL 查询、密钥管理、敏感请求 schema
审计日期：2026-06-06

## 严重 (CVSS >= 7)

### [backend/routes/common.py:47-68] JWT 采用可伪造的明文结构，缺少签名校验 (CVSS: 9.1)
- 攻击向量：攻击者只要知道任意一个有效成员的 id、role 和大致过期格式，就可以直接构造符合 `id:role:expires_at` 结构的 token，再把 `role` 改成 `admin` 或 `leader` 尝试越权。因为 token 没有 HMAC / RSA 签名，也没有 jti、issuer、audience 约束，服务端只能做字符串解析和数据库角色比对，无法证明 token 未被篡改。
- 影响：认证失效，攻击者可冒充任意已存在成员并伪造更高角色，进而访问创建、修改、删除活动/公告、成员管理等高权限接口，影响全站访问控制边界。
- 修复：
```python
from datetime import datetime, timedelta, timezone
import os
import jwt
from fastapi import HTTPException, Header, status

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = 'HS256'
JWT_ISSUER = 'runclub-api'
JWT_AUDIENCE = 'runclub-web'


def token_for_member(member: Member) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(member.id),
        'role': member.role,
        'iat': int(now.timestamp()),
        'exp': now + timedelta(hours=TOKEN_TTL_HOURS),
        'iss': JWT_ISSUER,
        'aud': JWT_AUDIENCE,
        'jti': secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def parse_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALG],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={'require': ['exp', 'iat', 'sub', 'role']},
        )
        member_id = int(payload['sub'])
        role = payload['role']
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc

    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/models.py:58-78, 159-173] 安全敏感创建模型未统一禁止额外字段 (CVSS: 8.1)
- 攻击向量：`ActivityCreate`、`AnnouncementCreate` 以及其基础模型未统一显式继承 `extra='forbid'` 的基类，导致未来新增字段或派生模型时，FastAPI/Pydantic 可能默认吞掉未知字段而不报 422。攻击者可借此把伪造字段塞进请求体，诱导后续代码在 `model_dump()` / `dict()` / 转换逻辑里错误传播非预期数据，形成权限绕过、业务字段污染或“补丁失效”问题。
- 影响：活动和公告创建接口的请求边界不稳定，输入验证失去封闭性；一旦后续代码复用这些模型，额外字段可能被错误接受并写入数据库或日志，造成数据污染和潜在越权。
- 修复：
```python
from pydantic import BaseModel, ConfigDict, Field

class ActivityBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)

class ActivityCreate(ActivityBase):
    pass

class AnnouncementBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: AnnouncementStatus = 'published'
    is_pinned: bool = False

class AnnouncementCreate(AnnouncementBase):
    pass
```

## 中等 (CVSS 4-6)

### [backend/routes/activities.py:18-24] 创建活动接口依赖运行时角色断言，存在授权逻辑重复与漂移风险 (CVSS: 6.1)
- 攻击向量：当前先调用 `admin_or_leader(current_user)`，后又重复判断 `current_user.role not in {ROLE_ADMIN, ROLE_LEADER}`。当未来某一处条件修改但另一处遗漏时，攻击者可利用一致性缺陷进入本不该开放的流程；此外重复分支扩大了审计面，容易在重构时引入“放行一条路径”的隐患。
- 影响：角色边界维护成本升高，后续修改极易出现授权漂移；一旦其中一层校验被改坏，创建活动就可能对普通成员开放。
- 修复：
```python
@router.post('', response_model=ApiResponse, status_code=201)
def create_activity_endpoint(payload: ActivityCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    activity = create_activity(payload)
    return ApiResponse(data=activity.model_dump(mode='json'))
```

### [backend/routes/announcements.py:18-23, 34-41] 公告创建/更新路径绕过原始 schema 约束的转换链过长 (CVSS: 5.8)
- 攻击向量：接口先接收 `AnnouncementCreate`/`AnnouncementUpdate`，再通过 `announcement_payload()` 重组为字典，最后重新实例化模型。这个“模型→字典→模型”的往返链条会扩大未来注入未知字段、字段名漂移和默认值被覆盖的风险，攻击者只需构造边界输入即可触发错误的字段映射路径。
- 影响：公告创建/更新的输入边界复杂化，容易出现字段别名错配、默认值被覆盖、后续新增字段被错误允许的问题；安全上会削弱“未知字段返回 422”的保证。
- 修复：
```python
@router.post('', response_model=ApiResponse, status_code=201)
def create_announcement_endpoint(payload: AnnouncementCreate = Body(...), current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    announcement = create_announcement(payload)
    return ApiResponse(data=announcement.model_dump(mode='json'))

@router.patch('/{announcement_id}', response_model=ApiResponse)
def patch_announcement(announcement_id: int, payload: AnnouncementUpdate = Body(...), current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    announcement = update_announcement(announcement_id, payload)
    if announcement is None:
        raise HTTPException(status_code=404, detail='announcement not found')
    return ApiResponse(data=announcement.model_dump(mode='json'))
```

### [backend/routes/common.py:71-80] 可选认证接口对空 Authorization 的处理不一致，容易误判为匿名可访问 (CVSS: 4.7)
- 攻击向量：`get_optional_current_user()` 在 header 缺失时直接返回 `None`，而部分接口再靠后续 `admin_or_leader()` 才拦截。攻击者可以反复试探哪些接口允许匿名进入调用链，扩大攻击面并制造认证/授权判定歧义。
- 影响：接口语义不一致，增加误配置和未来“补上一个依赖但漏掉一个 guard”的概率；在审计时容易把“缺少 token”与“匿名策略”混淆。
- 修复：
```python
def get_optional_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser | None:
    if not authorization:
        return None
    if not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    return parse_token(authorization.removeprefix('Bearer ').strip())
```

## 低危 (CVSS < 4)

### [backend/routes/checkins.py:14-16] 直接就地修改请求模型字段，破坏输入对象不可变语义 (CVSS: 3.3)
- 攻击向量：`_coerce_attendance_payload()` 会直接改写 `payload.activity_id`。如果未来同一对象被复用、缓存或记录日志，攻击者可借此触发“前后不一致”的业务状态，导致审计和回放误差。
- 影响：当前不一定形成直接漏洞，但会让输入对象在函数链中发生隐式变形，后续一旦加入审计日志或签名校验，就会出现难以追踪的不一致。
- 修复：
```python
from pydantic import BaseModel

def _coerce_attendance_payload(activity_id: int, payload: AttendanceCreate) -> AttendanceCreate:
    if payload.activity_id == activity_id:
        return payload
    return AttendanceCreate(
        member_id=payload.member_id,
        activity_id=activity_id,
        checked_in_at=payload.checked_in_at,
        gps_checked=payload.gps_checked,
    )
```

### [backend/routes/workspaces.py:23-38] 工作区路径归一化与遍历拒绝分散，存在双重校验漂移 (CVSS: 3.1)
- 攻击向量：`_reject_path_traversal()` 与 `_normalize_workspace_path()` 分离，前者仅检查 `..`，后者再做 `resolve(strict=False)`。攻击者可针对未来改动后的边界条件制造路径判断不一致，诱导文件/任务查询对非预期路径进行解析。
- 影响：当前主要是可维护性和未来安全风险；路径控制逻辑拆散会让后续补丁更容易遗漏一个分支。
- 修复：
```python
def _normalize_workspace_path(workspace_path: str) -> str:
    path = Path(unquote(workspace_path)).expanduser()
    if not path.is_absolute():
        raise HTTPException(status_code=422, detail='invalid workspace path')
    resolved = path.resolve(strict=False)
    if '..' in resolved.parts:
        raise HTTPException(status_code=422, detail='invalid workspace path')
    return str(resolved)
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [x] 当前代码未发现 `jwt_secret` / `api_key` / `secret` 明文硬编码
- [x] SQLite 查询使用参数化占位符
- [x] 敏感创建 schema 的 `extra='forbid'` 已在部分模型上落地，但 Activity/Create 与 Announcement/Create 需要统一收紧

## 结论
- 最高风险点是 JWT 伪造：一旦 token 可被篡改，所有基于角色的接口都会被连带击穿。
- 输入验证方面，Activity/Create 与 Announcement/Create 的未知字段封闭性需要统一收口，避免未来变更把“只接受已知字段”的边界重新打开。
- SQL 注入未见直接证据，SQLite 访问已使用参数化查询；当前主要风险集中在认证、授权与 schema 边界。
