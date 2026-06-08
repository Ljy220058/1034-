# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68] 明文 token 可伪造，缺少签名保护 (CVSS: 9.1)
- 攻击向量：攻击者一旦知道任意合法用户的 `id`、`role` 和 `expires_at` 格式，就可以直接构造新的 Bearer token；服务端只做分段解析和角色比对，没有任何 HMAC/JWT 签名校验，篡改 payload 后依然可能通过鉴权。
- 影响：任意用户可被冒充，角色可被伪造为 `admin`/`leader`，可直接访问高权限成员、活动和公告接口，属于完整的认证绕过。
- 修复：```python
from hashlib import sha256
import hmac
import os
from base64 import urlsafe_b64encode, urlsafe_b64decode
import json

TOKEN_SECRET = os.getenv('RUNNING_CLUB_TOKEN_SECRET')
if not TOKEN_SECRET:
    raise RuntimeError('RUNNING_CLUB_TOKEN_SECRET is required')


def token_for_member(member: Member) -> str:
    payload = {
        'sub': member.id,
        'role': member.role,
        'exp': int((utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    body = urlsafe_b64encode(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()).decode().rstrip('=')
    sig = hmac.new(TOKEN_SECRET.encode(), body.encode(), sha256).hexdigest()
    return f'{body}.{sig}'


def parse_token(token: str) -> CurrentUser:
    try:
        body, sig = token.rsplit('.', 1)
        expected = hmac.new(TOKEN_SECRET.encode(), body.encode(), sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError('bad signature')
        payload = json.loads(urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        member_id = int(payload['sub'])
        role = str(payload['role'])
        expires_at = datetime.fromtimestamp(int(payload['exp']), tz=timezone.utc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    if expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    ...
``` 
### [backend/routes/common.py:52-68] 仅校验 role 字段且未绑定签名，导致角色篡改可直接提权 (CVSS: 8.8)
- 攻击向量：攻击者修改 token 中的 `role` 为更高权限值，服务端仅检查数据库里的 `member.role != role`，但 token 本身没有真实性来源，且当前用户记录的角色变化并不能证明 token 未被篡改。
- 影响：普通成员可伪装成管理员/领队，绕过 `admin_or_leader()`、`member_read_guard()`、`member_write_guard()` 等授权中间件。
- 修复：```python
# 与上一个修复一致：将 role 作为签名 payload 的一部分，并在解析时进行签名校验
# 另外建议在 get_current_user 里把 token 解析结果与数据库记录的 role 强绑定
member = get_member(member_id)
if member is None or member.role != role:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
```
### [backend/routes/common.py:48-63] 令牌过期检查依赖可伪造 payload，过期字段可被任意重写 (CVSS: 7.8)
- 攻击向量：由于 `expires_at` 明文可编辑，攻击者可把过期 token 的 `expires_at` 改成未来时间，服务端在 `datetime.fromisoformat()` 后直接比较并放行。
- 影响：被盗 token 不会失效，攻击者可长期重放会话，提升横向移动窗口。
- 修复：```python
# 使用签名化 payload + 统一的 exp 时间戳验证
if expires_at <= utcnow():
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
```

## 中等 (CVSS 4-6)
### [backend/routes/auth.py:19-31] 注册仍使用 SHA-256 单轮哈希，离线撞库成本过低 (CVSS: 5.9)
- 攻击向量：数据库泄露后，攻击者可以对 `password_hash` 做高速 GPU 字典攻击；单轮 SHA-256 不具备密码哈希所需的计算和内存成本。
- 影响：会员密码被快速恢复，进一步用于登录和跨系统复用攻击。
- 修复：```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')

password_hash = pwd_context.hash(payload.password)
...
if not pwd_context.verify(payload.password, row['password_hash']):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```
### [backend/routes/announcements.py:18-23,34-41] 公告写接口接受可选认证，缺少统一鉴权入口导致未来重构时易引入未认证写入 (CVSS: 5.1)
- 攻击向量：当前依赖 `current_user | None = Depends(get_optional_current_user)` 再手工调用 `admin_or_leader()`；这类“可选认证 + 手工校验”模式在后续改动中容易出现漏调用，从而把写接口暴露给匿名用户。
- 影响：公告发布/修改/删除一旦漏掉 `admin_or_leader()` 就会变成未授权修改面，属于高风险设计缺陷。
- 修复：```python
@router.post('', response_model=ApiResponse, status_code=201)
def create_announcement_endpoint(payload: AnnouncementCreate = Body(...), current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    ...
```
### [backend/schemas.py:13-34] 输入验证未限制 phone 格式与部分字段语义，容易造成脏数据和授权绕行的前置条件 (CVSS: 4.3)
- 攻击向量：攻击者可提交任意字符串作为 phone、pace 等字段，污染用户主数据并干扰以 phone 为登录键的业务逻辑；如果后续引入基于格式的权限/匹配逻辑，脏值会放大成绕过条件。
- 影响：账号查找、登录、审计关联和通知发送稳定性下降，恶意数据可用于探测和持久化异常状态。
- 修复：```python
from pydantic import field_validator
import re

PHONE_RE = re.compile(r'^1\d{10}$')

class MemberBase(BaseModel):
    ...
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is not None and not PHONE_RE.fullmatch(v):
            raise ValueError('invalid phone format')
        return v
```

## 低危 (CVSS < 4)
### [backend/routes/common.py:71-80] get_optional_current_user 未区分空 header 和坏 token，错误语义过于宽泛 (CVSS: 3.1)
- 攻击向量：无效 Authorization 头会走到 `get_current_user()` 并返回统一 401；虽然不是直接漏洞，但错误类型不可区分，容易掩盖真实认证失败原因，增加运维排障成本。
- 影响：安全日志和监控难以区分“未登录”和“伪造 token”，降低入侵检测质量。
- 修复：```python
def get_optional_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser | None:
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] token 过期时间是否由服务端签名保护
- [ ] 是否存在单轮 SHA-256 口令哈希
- [ ] 是否对 Authorization 头做统一验证和审计记录
