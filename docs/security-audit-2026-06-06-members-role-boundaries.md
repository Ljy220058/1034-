# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/models.py:13-34, backend/routes/members.py:29-37] 成员创建/注册/更新暴露 role 字段并存在越权提权面 (CVSS: 8.8)
- 攻击向量：攻击者在注册、成员创建或资料更新请求中提交 role=admin/leader。MemberBase、MemberCreate、MemberUpdate 都公开了 role，members 路由再用运行时分支做降权/拦截；这种“模型允许 + 路由补丁式修正”的组合很容易在重构、复用或新增入口时漏掉检查，导致低权限用户把自己或他人提升为高权限角色。
- 影响：普通成员可尝试获得 leader/admin 权限，进而读取全量成员、创建/删除活动、操控签到与注册、访问所有管理接口。
- 修复：```python
# backend/models.py
class MemberBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: int = Field(default=0, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)

class MemberCreate(MemberBase):
    pass

class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)

# backend/routes/members.py
@router.post('', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_member_endpoint(payload: MemberCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    member = create_member(UserRegister(**payload.model_dump()))
    return ApiResponse(data=member_to_public(member))

@router.patch('/{member_id}', response_model=ApiResponse)
def patch_member(member_id: int, payload: MemberUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_write_guard(member_id, current_user)
    if current_user.role != ROLE_ADMIN and getattr(payload, 'role', None) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role changes are admin-only')
    payload = payload.model_copy(update={'role': None})
    member = update_member(member_id, payload)
    ...
```

### [backend/routes/common.py:36-44] 注册净化逻辑依赖类名分支，安全边界不可维护 (CVSS: 7.1)
- 攻击向量：sanitize_member_payload 通过 payload.__class__.__name__ == 'UserRegister' 来决定是否阻止 role。攻击者不需要直接绕过这个分支，只要后续新增别名、子类、测试替身、重构或数据适配层复用该函数，类名判断就会失去约束力，注册入口可能退化为默认接受角色字段。
- 影响：注册即提权会直接把新账号放进管理员权限组，属于认证入口的高危失效。
- 修复：```python
def sanitize_member_payload(payload: Any, *, allow_role: bool) -> dict[str, Any]:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    if not allow_role:
        data.pop('role', None)
        return data
    if data.get('role') not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid role')
    return data

# register()
member, outcome = create_member_with_password(
    sanitize_member_payload(payload, allow_role=False),
    password_hash,
)
```

## 中等 (CVSS 4-6)
### [backend/routes/auth.py:17-31, backend/routes/common.py:47-74] 访问令牌是无签名明文结构，缺少密钥和完整性保护 (CVSS: 6.8)
- 攻击向量：token 直接拼接为 member_id:role:expires_at，服务端只做 split 和数据库角色比对，没有 HMAC/签名校验。攻击者只要掌握 token 格式，就能篡改载荷字段并尝试构造看似有效的令牌，完整性完全依赖实现细节而不是密码学保护。
- 影响：认证边界脆弱，令牌被窃取或篡改后的风险显著上升，且无法抵御离线伪造尝试。
- 修复：```python
import base64
import hashlib
import hmac
import json
from backend.settings import settings

def token_for_member(member: Member) -> str:
    payload = {
        'sub': member.id,
        'role': member.role,
        'exp': int((utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    ).decode('ascii').rstrip('=')
    sig = hmac.new(settings.jwt_secret.encode('utf-8'), body.encode('ascii'), hashlib.sha256).hexdigest()
    return f'{body}.{sig}'

def parse_token(token: str) -> CurrentUser:
    body, sig = token.rsplit('.', 1)
    expected = hmac.new(settings.jwt_secret.encode('utf-8'), body.encode('ascii'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
```

### [backend/models.py:67-78, backend/models.py:166-171] 多个写接口允许 extra=allow，放大输入污染和逻辑注入面 (CVSS: 5.5)
- 攻击向量：活动与公告创建模型对未声明字段不拒绝，攻击者可在 JSON 里混入多余字段，诱导后续代码、日志、审计或未来补丁误用未验证数据。
- 影响：输入面扩大，后续开发更容易把“额外字段”带入业务逻辑，形成隐蔽的权限或状态污染。
- 修复：```python
class ActivityCreate(BaseModel):
    ...
    model_config = {'extra': 'forbid'}

class AnnouncementCreate(BaseModel):
    ...
    model_config = {'extra': 'forbid'}
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:19-43] 密码摘要使用裸 SHA-256，无盐和慢哈希 (CVSS: 3.9)
- 攻击向量：一旦数据库、备份或日志泄露，攻击者可直接对 SHA-256 摘要进行高速离线爆破，恢复弱口令。
- 影响：账号口令恢复成本过低，进一步放大认证与授权问题的后果。
- 修复：```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
password_hash = pwd_context.hash(payload.password)
if not pwd_context.verify(payload.password, row['password_hash']):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
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
- [x] A05 Security Misconfiguration
- [x] A06 Vulnerable and Outdated Components
- [x] A07 Identification and Authentication Failures
- [x] A08 Software and Data Integrity Failures
- [x] A09 Security Logging and Monitoring Failures
- [x] A10 Server-Side Request Forgery
