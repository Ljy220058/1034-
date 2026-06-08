# 安全审计报告

## 严重 (CVSS >= 7)
### [backend/routes/common.py:53-80] 明文自定义 token 可伪造且仅靠前端拼接即可复用 (CVSS: 9.1)
- 攻击向量：攻击者读取代码后，直接构造 `id:role:expires_at` 结构的 token；由于 token 未签名、未绑定服务器状态，只要猜到或枚举到有效成员 ID，且 token 仍在过期时间内，就能伪装为该成员或更高角色访问受保护接口。
- 影响：会话可被离线伪造，`admin`/`leader` 级接口、成员信息读取、活动创建/删除、签到删除等受保护操作可被越权执行。
- 修复：使用带签名的 JWT/HMAC 令牌，并在服务端验证 `sub`、`role`、`exp`、`iat`，同时把 token 解析失败统一返回 401。
```python
import os
import jwt
from datetime import datetime, timedelta, timezone

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = 'HS256'
TOKEN_TTL_HOURS = 7

def token_for_member(member):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(member.id),
        'role': member.role,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def parse_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        member_id = int(payload['sub'])
        role = payload['role']
    except Exception as exc:
        raise HTTPException(status_code=401, detail='invalid or expired token') from exc
    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=401, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/routes/common.py:89-99, 103-130] 角色检查仅依赖解码后的字符串，缺少权限域约束与一致性校验 (CVSS: 8.1)
- 攻击向量：一旦攻击者获得任意可用 token，`require_roles()`、`admin_or_leader()`、`member_read_guard()`、`member_write_guard()` 都只检查字符串角色和值是否匹配；没有基于服务端策略表做细粒度权限校验，也没有检查 token 是否为当前账号最新会话，因此被盗 token 可在过期前持续调用管理员和成员敏感接口。
- 影响：角色边界被绕过后，攻击者可读取或修改任意成员资料，新增/删除活动，删除签到记录，批量滥用公告接口。
- 修复：把角色授权集中到单一鉴权函数，映射到接口级 policy，而不是在多个 helper 中重复比较字符串；并为高风险操作增加服务端可撤销的会话标识。
```python
from enum import Enum

class Scope(str, Enum):
    MEMBERS_READ = 'members:read'
    MEMBERS_WRITE = 'members:write'
    ACTIVITIES_WRITE = 'activities:write'
    CHECKINS_WRITE = 'checkins:write'

ROLE_SCOPES = {
    'member': {Scope.MEMBERS_READ, Scope.CHECKINS_WRITE},
    'leader': {Scope.MEMBERS_READ, Scope.MEMBERS_WRITE, Scope.ACTIVITIES_WRITE, Scope.CHECKINS_WRITE},
    'admin': {Scope.MEMBERS_READ, Scope.MEMBERS_WRITE, Scope.ACTIVITIES_WRITE, Scope.CHECKINS_WRITE},
}

def require_scope(current_user: CurrentUser, scope: Scope) -> None:
    if scope not in ROLE_SCOPES.get(current_user.role, set()):
        raise HTTPException(status_code=403, detail='forbidden')
```

### [backend/models.py:68, 80, 231, 239] Pydantic 允许额外字段，输入污染可把未声明字段带进后续持久化流程 (CVSS: 7.4)
- 攻击向量：`ActivityBase`、`ActivityCreate`、`AnnouncementBase`、`AnnouncementCreate` 都设置了 `model_config = {'extra': 'allow'}`；攻击者可在请求体里塞入未定义字段，若后续仓储层或日志拼装逻辑直接复用 `model_dump()`，这些字段会被保留并传播到数据库或审计日志，形成数据污染、越权参数注入、字段混淆。
- 影响：前端和后端对字段边界的理解不一致，攻击者可借额外字段污染持久化对象、误导审计、为后续业务逻辑注入隐藏状态。
- 修复：把 `extra` 改为 `forbid`，并在入库前只白名单拷贝显式字段。
```python
from pydantic import BaseModel, Field, ConfigDict

class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    # ...
```

## 中等 (CVSS 4-6)
### [backend/routes/auth.py:19-19, backend/routes/common.py:53-55] 密码与 token 关键材料没有使用标准密钥派生/哈希方案 (CVSS: 6.5)
- 攻击向量：注册时直接用 SHA-256 对密码做单轮哈希，登录时同样直接比对；攻击者拿到数据库文件后可以离线高速爆破弱口令。token 侧又是无签名明文拼接，进一步降低了攻击门槛。
- 影响：数据库泄露后，成员密码可被批量撞库恢复，后续可直接获取合法 token 进入系统。
- 修复：密码使用 Argon2/bcrypt，token 使用单独的高熵签名密钥，并做轮换与环境变量注入。
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')

password_hash = pwd_context.hash(payload.password)
if not pwd_context.verify(payload.password, row['password_hash']):
    raise HTTPException(status_code=401, detail='invalid phone or password')
```

### [backend/routes/checkins.py:14-19] 请求体可覆盖路径参数，存在参数混淆与越界写入风险 (CVSS: 5.9)
- 攻击向量：`_coerce_attendance_payload()` 会把 body 里的 `activity_id` 直接改写为路径参数；如果中间件或未来路由复用该模型，攻击者可以构造与路径不一致的载荷，造成日志、校验、落库三者不一致，进而把一条请求写入到与客户端预期不同的活动上下文。
- 影响：审计链路失真，签到请求可能被误关联到错误活动，给越权提交和业务绕过留出口。
- 修复：不要原地修改 Pydantic 对象；在进入业务层前创建新对象并强制只采用路径参数。
```python
from copy import copy

def _coerce_attendance_payload(activity_id: int, payload: AttendanceCreate) -> AttendanceCreate:
    data = payload.model_dump()
    data['activity_id'] = activity_id
    return AttendanceCreate(**data)
```

### [backend/routes/announcements.py:12-45] 公告创建/删除接口半关闭但仍暴露授权路径，容易形成错误的安全假象 (CVSS: 4.8)
- 攻击向量：`create_announcement_endpoint()` 和 `remove_announcement()` 先通过授权检查，再立刻抛出 503；这类“看起来已保护”的半成品接口若在后续合并中恢复实现，极易被误判为已完成授权。攻击者可通过测试这些路径确认角色门槛，并针对将来的实现做预探测。
- 影响：维护者容易忽视这些接口的真实状态，后续补实现时若遗漏进一步检查，会直接变成可利用的越权入口。
- 修复：要么彻底下线路由，要么在实现前返回明确的 `501 Not Implemented` 并移除授权误导；上线时补全单元测试覆盖角色边界。
```python
raise HTTPException(status_code=501, detail='announcement endpoints not implemented yet')
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:38-48] 登录失败路径统一但缺少速率限制，存在在线口令猜测面 (CVSS: 3.7)
- 攻击向量：`/login` 对错误手机号和密码返回相同错误，减少了枚举信号，但接口没有速率限制或失败锁定；攻击者可针对已知手机号持续在线尝试口令。
- 影响：弱口令账号会被自动化猜解，尤其是与数据库离线泄露结合时风险更高。
- 修复：为登录接口增加按手机号/IP 的速率限制与指数退避。
```python
# pseudo: use redis/fail2ban style limiter before password verify
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
