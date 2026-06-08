# Security Audit Report

## Severe (CVSS >= 7)

### [backend/database.py:16-27, backend/routes/auth.py:19-43] Unsalted SHA-256 password storage and verification (CVSS: 9.1)
- 攻击向量：攻击者一旦拿到数据库、备份、日志导出或任意能读取 `members.password_hash` 的路径，就可以对 SHA-256 哈希做离线爆破/彩虹表撞库；因为哈希没有盐且计算极快，弱口令和复用口令会被快速恢复。
- 影响：成员账号可被批量接管；一旦某个密码被恢复，攻击者可以直接登录并获取对应成员的访问令牌，进一步冒用该身份访问业务接口。
- 修复：
```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=['argon2'],
    deprecated='auto',
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> ApiResponse:
    password_hash = hash_password(payload.password)
    ...


@router.post('/login', response_model=ApiResponse)
def login(payload: UserLogin) -> ApiResponse:
    ...
    if row is None or not row['password_hash']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    if not verify_password(payload.password, row['password_hash']):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    ...
```

### [backend/database.py:16-27] Legacy password schema keeps plaintext-compatible field without migration/rehash policy (CVSS: 7.5)
- 攻击向量：即使后续改成慢哈希，只要旧记录仍保留在 `password_hash` 字段里且没有统一迁移，历史账号仍可能沿用弱哈希；攻击者可优先针对旧账户进行离线破解，并在系统内长期利用未升级凭据。
- 影响：新旧账号安全强度不一致，审计中无法证明所有账号已被提升到同一安全基线；弱账号将成为持续突破口。
- 修复：
```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')


def verify_and_upgrade(password: str, stored_hash: str) -> tuple[bool, str]:
    verified, new_hash = pwd_context.verify_and_update(password, stored_hash)
    return verified, new_hash or stored_hash


@router.post('/login', response_model=ApiResponse)
def login(payload: UserLogin) -> ApiResponse:
    ...
    verified, upgraded_hash = verify_and_upgrade(payload.password, row['password_hash'])
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    if upgraded_hash != row['password_hash']:
        with connect() as connection:
            connection.execute(
                'UPDATE members SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (upgraded_hash, row['id']),
            )
    ...
```

## Medium (CVSS 4-6)

### [backend/routes/auth.py:38-44] Username enumeration via distinguishable auth path timing/branching (CVSS: 5.9)
- 攻击向量：攻击者可通过批量提交不同手机号，利用“用户不存在/密码错误”分支和密码哈希校验的耗时差异，逐步枚举有效手机号并筛选活跃账号。
- 影响：账号目录泄露会显著降低后续撞库、钓鱼和社工攻击成本；也会帮助攻击者聚焦高价值目标。
- 修复：
```python
# backend/routes/auth.py
DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzYW1wbGU$uVhG4gZ9b0g7tT4x5wqB2r7j6V5L3kqJ2uYQbK1v4JQ'


def login(payload: UserLogin) -> ApiResponse:
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE phone = ?', (payload.phone,)).fetchone()
    stored_hash = row['password_hash'] if row and row['password_hash'] else DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    if row is None or row['password_hash'] is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    ...
```

### [backend/routes/common.py:47-68] Stateless bearer token is not signed and can be forged if format is guessed (CVSS: 6.8)
- 攻击向量：令牌内容仅为 `member_id:role:expires_at` 的明文拼接，没有签名、没有密钥校验、没有服务端 nonce；攻击者只要猜到合法格式并能构造未来过期时间，就可以伪造任意成员角色令牌。
- 影响：权限边界失效，攻击者可冒充管理员或队长访问受限接口、读取敏感成员数据并进行管理操作。
- 修复：
```python
# backend/routes/common.py
from itsdangerous import BadSignature, URLSafeTimedSerializer
from fastapi import HTTPException, status
from ..settings import get_settings


def _token_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.jwt_secret, salt='auth-token')


def token_for_member(member: Member) -> str:
    return _token_serializer().dumps({'member_id': member.id, 'role': member.role})


def parse_token(token: str) -> CurrentUser:
    try:
        data = _token_serializer().loads(token, max_age=TOKEN_TTL_HOURS * 3600)
    except BadSignature as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    member = get_member(int(data['member_id']))
    if member is None or member.role != data['role']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/routes/common.py:83-115] Role guard depends on caller-supplied `current_user` and has no centralized dependency enforcement (CVSS: 5.4)
- 攻击向量：如果任一新路由忘记在函数签名里注入 `current_user` 或直接调用业务函数而绕过装饰器，角色检查就不会执行；攻击者只需找到漏挂保护的新接口即可横向越权。
- 影响：授权边界脆弱，随着代码增长极易出现“默认公开”的管理接口，导致成员数据和管理操作被未授权访问。
- 修复：
```python
# backend/routes/common.py
from fastapi import Depends


def require_roles(*roles: str):
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, current_user: CurrentUser = Depends(get_current_user), **kwargs: Any):
            if current_user.role not in roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
            return func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

## Low (CVSS < 4)

### [backend/models.py:42-49] Password length policy is generic and does not reject common weak-password patterns (CVSS: 3.2)
- 攻击向量：攻击者对短口令、字典口令、手机号后6位等常见模式进行撞库时，系统没有任何复杂度或黑名单限制，弱口令会被轻易接受并长期保留。
- 影响：提高口令可猜测性，放大离线破解与在线撞库的成功率。
- 修复：
```python
# backend/models.py
from pydantic import field_validator
import re

class UserRegister(MemberBase):
    phone: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('password')
    @classmethod
    def password_policy(cls, value: str) -> str:
        if re.fullmatch(r'\d{6,}', value):
            raise ValueError('password is too weak')
        return value
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] 是否存在未签名/可伪造 token
- [ ] 是否为密码哈希使用 Argon2/bcrypt/scrypt 这类慢哈希
- [ ] 是否对旧密码哈希做迁移/升级
