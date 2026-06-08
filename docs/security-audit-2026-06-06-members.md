# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68] 无签名自制 token 可伪造角色并越权 (CVSS: 8.8)
- 攻击向量：攻击者只要知道或猜到任意有效 member_id、当前 role 和未过期时间格式，就能直接构造与服务端格式一致的 Bearer token；parse_token 只做分隔、过期时间和数据库角色比对，没有 MAC/签名，token 本身可被离线伪造。
- 影响：攻击者可在 token 有效期内冒充 leader/admin/member，读取成员列表、创建/修改成员、操作活动与公告等所有依赖 get_current_user 的接口。
- 修复：```python
import hmac
import hashlib
import json
import base64
from datetime import timedelta

SECRET_KEY = os.getenv('JWT_SECRET', '')
if not SECRET_KEY:
    raise RuntimeError('JWT_SECRET is required')

def token_for_member(member: Member) -> str:
    expires_at = (utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    payload = {'sub': member.id, 'role': member.role, 'exp': expires_at}
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
    sig = hmac.new(SECRET_KEY.encode(), body, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(body).decode() + '.' + sig

def parse_token(token: str) -> CurrentUser:
    body_b64, sig = token.split('.', 1)
    body = base64.urlsafe_b64decode(body_b64.encode())
    expected = hmac.new(SECRET_KEY.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail='invalid or expired token')
    payload = json.loads(body)
    ...
```

### [backend/models.py:18-35, backend/routes/members.py:29-36,54-63] 成员创建/更新把 role 暴露给普通写入路径 (CVSS: 7.8)
- 攻击向量：MemberCreate/MemberUpdate 直接接收 role，路由里仅靠运行时分支修正；一旦其他调用点复用 schema、遗漏分支或未来新增创建/更新入口，攻击者即可把 role 提交为 admin/leader 试图提权。
- 影响：成员管理接口的授权边界被输入字段污染，后续维护很容易引入水平/垂直越权；当前实现还把“允许什么角色”分散在 schema、路由和 helper 三处，审计和复用都不安全。
- 修复：```python
# backend/models.py
class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: int = Field(default=0, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)

class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)

# backend/routes/members.py
def create_member_endpoint(payload: MemberCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    member = create_member(UserRegister(**payload.model_dump(), role='member'))
    return ApiResponse(data=member_to_public(member))

def patch_member(member_id: int, payload: MemberUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_write_guard(member_id, current_user)
    if current_user.role != ROLE_ADMIN and 'role' in payload.model_fields_set:
        raise HTTPException(status_code=403, detail='forbidden')
    ...
```

## 中等 (CVSS 4-6)
### [backend/routes/common.py:36-44] 注册/成员写入的角色规范靠字符串分支，缺少统一后端决策点 (CVSS: 5.6)
- 攻击向量：攻击者通过不同入口提交同一 role 字段，绕过点依赖 payload.__class__.__name__ 和手写 if/else；只要未来新增一个看似合法的模型或别名，就可能把 role 决策带离授权中间件。
- 影响：角色控制逻辑分散，容易出现“注册只允许 member，但创建接口默认允许更高角色”的不一致，造成权限漂移和维护期越权。
- 修复：```python
ROLE_CREATE_RULES = {'UserRegister': ROLE_MEMBER, 'MemberCreate': ROLE_MEMBER, 'MemberUpdate': None}

def sanitize_member_payload(payload: Any) -> Any:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    allowed_role = ROLE_CREATE_RULES.get(payload.__class__.__name__)
    if allowed_role is None:
        data.pop('role', None)
        return data
    if data.get('role') != allowed_role:
        raise HTTPException(status_code=403, detail='forbidden')
    data['role'] = allowed_role
    return data
```

### [backend/database.py:16-27, backend/routes/auth.py:19-44] 密码使用 SHA-256 直存，缺少专用密码哈希 (CVSS: 5.9)
- 攻击向量：一旦数据库泄露，攻击者可对所有密码哈希做高速离线破解；SHA-256 没有盐和工作因子，撞库成本极低。
- 影响：成员账号可批量被恢复明文密码，进一步接管管理员会话并横向移动到全部业务接口。
- 修复：```python
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')

# register
password_hash = pwd_ctx.hash(payload.password)
# login
if not pwd_ctx.verify(payload.password, row['password_hash']):
    raise HTTPException(status_code=401, detail='invalid phone or password')
```

## 低危 (CVSS < 4)
### [backend/routes/common.py:71-80] Authorization 解析未容错大小写与多空格，客户端兼容性差 (CVSS: 3.1)
- 攻击向量：合法客户端如果发送非标准 Authorization 头格式，会被直接拒绝；攻击者可借此诱导部分客户端产生误判式登录失败。
- 影响：可用性受影响，安全边界本身不破坏，但认证稳定性下降。
- 修复：```python
def get_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=401, detail='missing bearer token')
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise HTTPException(status_code=401, detail='missing bearer token')
    return parse_token(token.strip())
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore

## OWASP Top 10 覆盖
- [x] A01 Broken Access Control
- [x] A02 Cryptographic Failures
- [x] A03 Injection
- [x] A04 Insecure Design
- [ ] A05 Security Misconfiguration
- [x] A07 Identification and Authentication Failures
- [ ] A08 Software and Data Integrity Failures
- [ ] A09 Security Logging and Monitoring Failures
- [ ] A10 Server-Side Request Forgery
