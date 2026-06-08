# 安全审计报告

## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68] 认证 token 未签名，攻击者可伪造任意身份与角色 (CVSS: 9.8)
- 攻击向量：`token_for_member()` 直接拼接 `member.id:member.role:expires_at`，`parse_token()` 仅做字符串分割、时间解析和数据库角色比对，没有任何完整性校验。攻击者只要知道 token 格式，就可以自行构造 Bearer token，把 `role` 改成 `admin` 或 `leader`，并在过期前直接访问所有受保护接口。
- 影响：全站认证边界失效。成员管理、活动管理、公告管理、任务队列工人接入等管理接口都可被冒充调用，造成完整越权。
- 修复：```python
# backend/routes/common.py
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

TOKEN_SECRET = os.getenv('AUTH_TOKEN_SECRET')
if not TOKEN_SECRET:
    raise RuntimeError('AUTH_TOKEN_SECRET is required')


def token_for_member(member: Member) -> str:
    expires_at = int((utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    payload = f'{member.id}:{member.role}:{expires_at}'
    sig = hmac.new(TOKEN_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'{payload}:{sig}'


def parse_token(token: str) -> CurrentUser:
    try:
        member_id_str, role, expires_at_str, sig = token.split(':', 3)
        payload = f'{member_id_str}:{role}:{expires_at_str}'
        expected = hmac.new(TOKEN_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError('bad signature')
        member_id = int(member_id_str)
        expires_at = datetime.fromtimestamp(int(expires_at_str), tz=timezone.utc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc

    if expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')

    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
``` 

### [backend/routes/auth.py:18-19, 34-49] 密码使用 SHA-256 直哈希，缺少盐和慢哈希 (CVSS: 8.0)
- 攻击向量：注册时直接 `sha256(password)`，登录时再次直接比对。只要数据库、备份或调试导出泄露，攻击者就可以离线高速爆破所有口令，彩虹表和撞库效率都很高。
- 影响：账号接管风险显著上升，攻击者可恢复弱口令并登录后窃取 Bearer token，进一步访问成员资料、活动和公告接口。
- 修复：```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> ApiResponse:
    password_hash = pwd_context.hash(payload.password)
    ...

@router.post('/login', response_model=ApiResponse)
def login(payload: UserLogin) -> ApiResponse:
    ...
    if not pwd_context.verify(payload.password, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```

## 中等 (CVSS 4-6)
### [backend/routes/auth.py:34-49] 登录接口缺少速率限制与失败锁定 (CVSS: 5.3)
- 攻击向量：`/api/v1/auth/login` 没有限流、失败次数封禁或验证码。攻击者可以对手机号字典做在线口令喷洒，持续尝试直到命中弱口令。
- 影响：普通成员账号易被接管；一旦账号被盗，攻击者可继续利用已签发 token 访问个人资料和受限接口。
- 修复：```python
# backend/routes/auth.py
if not rate_limiter.allow(payload.phone, client_ip):
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='too many attempts')

# 在成功和失败分支中分别记录计数；连续失败后短暂封禁账号或 IP
```

### [backend/routes/common.py:52-68] token 缺少会话标识，无法单独吊销，重放窗口固定存在 (CVSS: 6.5)
- 攻击向量：token 只包含 `id/role/expires_at`，没有 `jti` 或会话状态。即使攻击者只是短暂窃取一次 token，也可以在 TTL 内反复重放；管理员也无法精准吊销某一次登录会话。
- 影响：会话劫持持续时间过长，账号失陷后不能立刻失效，安全运营无法做单会话踢下线。
- 修复：```python
# backend/routes/common.py
import uuid

def token_for_member(member: Member) -> str:
    expires_at = int((utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    jti = uuid.uuid4().hex
    payload = f'{member.id}:{member.role}:{expires_at}:{jti}'
    sig = hmac.new(TOKEN_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    store_session(member.id, jti, expires_at)
    return f'{payload}:{sig}'

# parse_token() 必须校验 jti 是否存在且处于 active 状态
```

### [backend/routes/members.py:29-37, 54-66] 成员创建/更新对角色输入的收敛不够集中，权限约束依赖路由分支 (CVSS: 5.9)
- 攻击向量：`MemberCreate` 和 `MemberUpdate` 直接暴露 `role` 字段，路由里通过手写分支限制普通用户。只要未来新增一个复用这些 schema 的入口，或某处漏掉角色限制，就会把角色提升逻辑带进去。
- 影响：后续扩展时容易引入权限提升；审计时需要逐个调用点验证，边界不够集中。
- 修复：```python
# backend/schemas.py
class MemberCreate(MemberBase):
    role: Literal['member'] = 'member'

class MemberUpdate(BaseModel):
    ...
    role: Optional[Literal['member']] = None

# backend/routes/members.py
# 将管理员角色变更拆成专门的 admin-only endpoint 或 admin-only schema
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:38-49] 登录成功后缺少登录审计记录 (CVSS: 3.5)
- 攻击向量：攻击者成功撞库或接管账号后，系统不会留下可检索的登录事件，安全团队难以及时发现异常登录来源、异常时间和爆破行为。
- 影响：事后取证和告警能力下降，入侵发现时间被拉长。
- 修复：```python
# backend/routes/auth.py
record_login_event(member.id, payload.phone, success=True)
# 失败路径也应记录，但要做速率限制，避免日志噪声
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] AUTH_TOKEN_SECRET 是否至少 32 字节随机值
- [ ] 是否禁止把 token、密码哈希写入日志
- [ ] 是否为可撤销会话保存 jti/session 状态
