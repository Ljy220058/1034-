# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/routes/auth.py:18-31, backend/routes/common.py:36-44, backend/models.py:42-45] 注册接口可被 role 参数提权 (CVSS: 8.8)
- 攻击向量：未认证攻击者在注册请求中提交 role=admin 或 role=leader；`UserRegister` 继承 `MemberBase` 接受 role 字段，而 `sanitize_member_payload()` 仅在注册路径里做了基于类名的特殊判断，导致注册模型与通用成员模型共享了可被篡改的 role 输入面。
- 影响：攻击者可直接创建高权限账号，随后调用管理员接口、篡改成员资料、读取受限成员列表，形成完整的认证后横向移动入口。
- 修复：```python
# backend/models.py
class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: int = Field(default=0, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)
    model_config = {'extra': 'forbid'}

class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)
    model_config = {'extra': 'forbid'}

class UserRegister(MemberCreate):
    password: str = Field(min_length=6, max_length=128)

# backend/routes/common.py

def sanitize_member_payload(payload: Any) -> dict[str, Any]:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    data['role'] = ROLE_MEMBER
    return data
```
### [backend/routes/members.py:29-37, 54-63, backend/models.py:28-35] 成员创建/更新接口接受并处理 role，存在角色边界绕过 (CVSS: 8.1)
- 攻击向量：已认证用户向 `/api/v1/members` 或 `/api/v1/members/{id}` 提交 role=leader/admin。创建接口中 `MemberCreate` 公开了 role 字段，更新接口中 `MemberUpdate` 也允许 role 写入，路由层只是做了运行时补丁式校验；一旦模型、路由或后续重构遗漏该分支，提权就会重新出现。
- 影响：普通成员可尝试把自己或新建成员提升为管理员/领队，破坏授权边界；管理员接口和受限成员列表会被间接暴露。
- 修复：```python
# backend/models.py
class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: int = Field(default=0, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)
    model_config = {'extra': 'forbid'}

class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)
    model_config = {'extra': 'forbid'}

# backend/routes/members.py
@router.post('', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_member_endpoint(payload: MemberCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    member = create_member(UserRegister(**payload.model_dump()))
    return ApiResponse(data=member_to_public(member))

@router.patch('/{member_id}', response_model=ApiResponse)
def patch_member(member_id: int, payload: MemberUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_write_guard(member_id, current_user)
    member = update_member(member_id, payload)
    ...
```
## 中等 (CVSS 4-6)
### [backend/routes/common.py:47-68] JWT 令牌为可读明文拼接，缺少签名与重放防护 (CVSS: 6.5)
- 攻击向量：攻击者只要拿到一个 token 字符串，就能直接读取 member_id、role 和过期时间，并且 token 只依赖服务端数据库当前角色状态；一旦 token 在日志、浏览器历史或代理缓存中泄露，攻击者可在 TTL 内重放。
- 影响：访问令牌泄露后的影响面扩大，角色信息明文暴露，令牌不可吊销性导致会话管理能力不足。
- 修复：```python
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

serializer = URLSafeTimedSerializer(SECRET_KEY, salt='auth-token')

def token_for_member(member: Member) -> str:
    return serializer.dumps({'member_id': member.id, 'role': member.role})

def parse_token(token: str) -> CurrentUser:
    try:
        data = serializer.loads(token, max_age=TOKEN_TTL_HOURS * 3600)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    member = get_member(int(data['member_id']))
    if member is None or member.role != data['role']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```
### [backend/routes/auth.py:19, 42] 密码仅使用 SHA-256 存储，缺少加盐和慢哈希 (CVSS: 5.9)
- 攻击向量：攻击者获取数据库后可对 `password_hash` 进行高速离线穷举和彩虹表撞库；明文手机号作为登录标识进一步放大账号猜测效率。
- 影响：一旦数据库泄露，弱口令成员会被快速恢复，进而被用于二次登录、数据导出和权限滥用。
- 修复：```python
import secrets
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')

# register
password_hash = pwd_context.hash(payload.password)

# login
if not pwd_context.verify(payload.password, expected):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```
## 低危 (CVSS < 4)
### [backend/routes/common.py:36-44] 依赖类名判断注册路径，授权逻辑耦合脆弱 (CVSS: 3.7)
- 攻击向量：后续重构或新增注册模型时，如果类名不再恰好等于 `UserRegister`，现有的“注册禁止提权”分支会失效，造成规则漂移。
- 影响：安全约束埋在字符串比较里，代码演进时容易被误删或绕过，导致同类提权复发。
- 修复：```python
# 用显式参数替代类名判断

def sanitize_member_payload(payload: Any, *, allow_role: bool = False) -> dict[str, Any]:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    if not allow_role:
        data.pop('role', None)
        data['role'] = ROLE_MEMBER
    return data
```
## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] 密码哈希是否使用加盐慢哈希
- [ ] 访问令牌是否支持签名和过期校验
