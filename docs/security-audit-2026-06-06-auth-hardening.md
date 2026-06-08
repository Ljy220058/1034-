# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/routes/auth.py:19-24, 42-44] 登录口令使用 SHA-256 直写哈希，缺少慢哈希与迁移保护 (CVSS: 8.8)
- 攻击向量：攻击者一旦拿到数据库中的 password_hash，就能对常见口令做高速离线撞库；登录时只做一次 SHA-256 比对，GPU/ASIC 可在短时间内批量破解弱口令。
- 影响：任意账号被快速接管，管理员/leader 账号一旦弱口令泄露会直接导致全站权限失陷。
- 修复：
```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

ph = PasswordHasher()

# register
password_hash = ph.hash(payload.password)

# login
stored = row['password_hash']
try:
    if stored.startswith('$argon2'):
        ph.verify(stored, payload.password)
    else:
        # 兼容旧 SHA-256 账户：只用于首次登录迁移
        legacy = hashlib.sha256(payload.password.encode('utf-8')).hexdigest()
        if not hmac.compare_digest(stored, legacy):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
        new_hash = ph.hash(payload.password)
        # 将 new_hash 持久化回 members.password_hash
except (VerifyMismatchError, VerificationError):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```

### [backend/routes/common.py:47-68] 访问令牌不是 JWT，只是可伪造的明文拼接串 (CVSS: 9.1)
- 攻击向量：token 仅包含 `member_id:role:expires_at`，没有签名/加密；只要知道任意有效 member_id 和 role，攻击者就能离线构造符合格式的 Authorization 值并冒充该身份直到过期。
- 影响：认证被完全绕过，攻击者可伪造 admin/leader 身份访问受保护接口，读取和修改成员、活动、公告与报名数据。
- 修复：
```python
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status
from .settings import get_settings

settings = get_settings()
ALGORITHM = 'HS256'


def token_for_member(member: Member) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(member.id),
        'role': member.role,
        'iat': int(now.timestamp()),
        'exp': now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def parse_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        member_id = int(payload['sub'])
        role = payload['role']
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/settings.py:9-10, 130-134] 配置缺少强制密钥校验与 JWT secret 管理 (CVSS: 7.5)
- 攻击向量：当前设置只要求数据库路径环境变量，认证所需的 secret 未见强制读取；一旦 secret 退回默认值、硬编码或从源码推断，攻击者可批量伪造 token。
- 影响：签名机制形同虚设，所有依赖 token 的授权边界都会失效。
- 修复：
```python
from pydantic import BaseModel, Field

class Settings(BaseModel):
    project_root: Path
    workspace_root: Path | None = None
    database_path: Path = DEFAULT_DB_PATH
    jwt_secret: str = Field(min_length=32)


def get_settings() -> Settings:
    return Settings(
        project_root=Path.cwd(),
        workspace_root=bootstrap.workspace_root,
        database_path=database_path,
        jwt_secret=os.environ['JWT_SECRET'],
    )
```

## 中等 (CVSS 4-6)
### [backend/routes/common.py:71-80] 认证头解析未支持标准 Bearer 变体与显式空白校验，易引发兼容性和误判 (CVSS: 5.3)
- 攻击向量：客户端若发送前导空格、大小写差异或多余空白，当前实现会直接拒绝，促使开发者在上层绕过认证或在网关层做不一致处理，扩大攻击面。
- 影响：认证栈行为不一致，容易在代理/网关/测试环境之间出现“本地可用、生产失效”的安全绕行。
- 修复：
```python
def get_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    return parse_token(token.strip())
```

### [backend/schemas.py:13-34] 用户输入缺少手机号与角色的约束，导致认证/授权边界依赖业务代码兜底 (CVSS: 5.0)
- 攻击向量：`phone` 仅限制长度，没有格式校验；`role` 由可变字符串集合表示，攻击者可提交奇异值触发不同路径的错误处理，增加越权与数据污染机会。
- 影响：账号唯一性、身份映射与角色判定更容易出现异常状态，认证失败分支和授权分支的覆盖面不足。
- 修复：
```python
from pydantic import BaseModel, Field, constr

PhoneStr = constr(pattern=r'^1\d{10}$')

class MemberBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: PhoneStr | None = None
    role: MemberRole = 'member'
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:17-31] 注册接口对密码复杂度未做最小约束 (CVSS: 3.7)
- 攻击向量：攻击者可用极弱口令注册并在口令重用场景下更容易被撞库命中。
- 影响：降低整体账号安全基线，配合当前弱哈希会显著放大爆破收益。
- 修复：
```python
from pydantic import Field, SecretStr

class UserRegister(...):
    password: SecretStr = Field(min_length=12, max_length=128)
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] 旧版 SHA-256 口令哈希是否已迁移完成
- [ ] 认证令牌是否已改为带签名的 JWT / PASETO
