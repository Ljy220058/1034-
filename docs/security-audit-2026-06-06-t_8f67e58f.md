# 安全审计报告

## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68] 认证令牌未签名，攻击者可伪造任意身份 (CVSS: 9.8)
- 攻击向量：攻击者只要知道或猜到合法的 `user_id:role:expires_at` 格式，就能自行构造 bearer token；`parse_token()` 只做格式拆分、过期时间检查和数据库中用户存在/角色匹配检查，没有任何完整性保护。攻击者可直接提升为任意 `member_id`，并冒充 `admin`/`leader` 访问管理接口。
- 影响：完整身份伪造、越权读取/修改成员资料、创建或删除活动、发布公告，直接导致全站认证与授权失效。
- 修复：```python
# backend/routes/common.py
import hmac
import hashlib
import os
from fastapi import Header, HTTPException, status

TOKEN_SECRET = os.getenv('AUTH_TOKEN_SECRET')
if not TOKEN_SECRET:
    raise RuntimeError('AUTH_TOKEN_SECRET is required')


def token_for_member(member: Member) -> str:
    expires_at = (utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    payload = f'{member.id}:{member.role}:{expires_at}'
    sig = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f'{payload}:{sig}'


def parse_token(token: str) -> CurrentUser:
    try:
        member_id_str, role, expires_at_str, sig = token.split(':', 3)
        payload = f'{member_id_str}:{role}:{expires_at_str}'
        expected = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError('bad signature')
        member_id = int(member_id_str)
        expires_at = datetime.fromisoformat(expires_at_str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc

    # keep DB role/session-state validation here
    ...
```

### [backend/routes/common.py:71-80, 83-101, 104-124] 授权中间件仅依赖 token 里的 role，未校验会话/禁用状态 (CVSS: 8.1)
- 攻击向量：即使修复了签名，当前 `get_current_user()` / `admin_or_leader()` / `member_read_guard()` / `member_write_guard()` 仍然只信任 token 中的角色字段和 `get_member()` 返回值；如果账号已被封禁、降权、删除后重新创建，旧 token 仍可能在 TTL 内继续使用。只要攻击者持有有效 token，就能在权限变更后继续越权访问。
- 影响：撤权不生效，封禁账号仍可持续操作；权限回收窗口内可继续执行敏感 API，破坏最小权限和应急封禁能力。
- 修复：```python
# backend/routes/common.py
from ..repository import get_member, get_active_session  # 或等价会话状态查询


def parse_token(token: str) -> CurrentUser:
    ...
    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    if getattr(member, 'status', 'active') != 'active':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    # if you persist sessions, validate the jti/session record here as well
    # if not is_session_active(member_id, sig_or_jti):
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/routes/auth.py:18-19, 34-43] 密码哈希使用 SHA-256，缺少盐和慢哈希 (CVSS: 8.0)
- 攻击向量：攻击者一旦拿到数据库或离线备份，就能对 `sha256(password)` 进行高速暴力破解和彩虹表碰撞；由于注册和登录都直接使用 SHA-256，弱口令会被快速恢复。
- 影响：账号接管、横向移动到高权限成员、批量撞库成功率显著升高。
- 修复：```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def register(payload: UserRegister) -> ApiResponse:
    password_hash = pwd_context.hash(payload.password)
    ...


def login(payload: UserLogin) -> ApiResponse:
    ...
    expected = row['password_hash']
    if not pwd_context.verify(payload.password, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```

## 中等 (CVSS 4-6)
### [backend/routes/common.py:52-68] token 结构可被重放且缺少会话标识，无法单独吊销 (CVSS: 6.5)
- 攻击向量：token 只包含 `user_id/role/expires_at`，没有 `jti/session_id`；即使后续补上签名，服务器也无法针对单个登录会话做吊销。攻击者窃取一次 token 后可在 TTL 内反复重放，管理员也无法精准踢下线。
- 影响：会话劫持时间窗口过长，账号被盗后难以立即失效，安全运营无法做单会话封禁。
- 修复：```python
# backend/routes/common.py
import uuid

def token_for_member(member: Member) -> str:
    expires_at = (utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    jti = uuid.uuid4().hex
    payload = f'{member.id}:{member.role}:{expires_at}:{jti}'
    sig = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    store_session(member.id, jti, expires_at)
    return f'{payload}:{sig}'

# parse_token() must verify the jti exists, is active, and matches the user/session state
```

### [backend/routes/members.py:29-37, 54-66] 成员创建/更新路径允许角色输入，权限边界依赖手工分支而非 schema 收敛 (CVSS: 5.9)
- 攻击向量：`MemberCreate` 和 `MemberUpdate` 直接暴露 `role`，路由里靠分支逻辑限制普通用户；只要未来出现一处调用遗漏或新接口复用该 schema，就会把角色提升逻辑带进去。当前设计把安全约束放在路由而不是输入层，容易被新代码绕过。
- 影响：后续扩展时容易引入权限提升；审计难度变高，任何新调用点都必须重新实现角色限制。
- 修复：```python
# backend/schemas.py
class MemberCreate(MemberBase):
    role: Literal['member'] = 'member'

class MemberUpdate(BaseModel):
    ...
    role: Optional[Literal['member']] = None

# backend/routes/members.py
# keep privileged role changes in a dedicated admin-only endpoint or admin-only schema
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:38-49] 登录成功后未记录登录审计信息 (CVSS: 3.5)
- 攻击向量：攻击者成功撞库或接管账号后，系统不会生成可追踪的登录事件，安全团队难以及时发现异常地理位置、设备指纹或爆破行为。
- 影响：入侵检测和事后取证能力下降，账号失陷时间延长。
- 修复：```python
# backend/routes/auth.py
record_login_event(member.id, payload.phone, success=True)
# failure paths should also log with rate-limited, privacy-safe metadata
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] AUTH_TOKEN_SECRET 是否至少 32 字节随机值
- [ ] 是否禁止把 token、密码哈希写入日志
- [ ] 是否为可撤销会话保存 jti/session 状态
