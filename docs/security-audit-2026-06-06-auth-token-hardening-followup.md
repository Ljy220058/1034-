# 安全审计报告

## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68] 认证令牌未签名且可伪造 (CVSS: 9.1)
- 攻击向量：攻击者只要知道任意合法成员的 id、role、expires_at 格式，就能直接构造看似有效的 Bearer token，并把角色伪造成 admin/leader 后访问需要高权限的接口。
- 影响：所有依赖 `get_current_user`、`admin_or_leader`、`member_read_guard`、`member_write_guard`、`registration_member_guard` 的权限边界全部失效，攻击者可读取、修改或删除成员、活动、报名、签到与公告数据。
- 修复：使用 HMAC/JWT 对 token 载荷签名，并在校验时严格验证签名、到期时间、签发时间与角色；签名密钥必须来自环境变量，不能硬编码。
```python
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

TOKEN_TTL_HOURS = 7
TOKEN_SECRET = os.environ["AUTH_TOKEN_SECRET"]


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def token_for_member(member: Member) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": member.id,
        "role": member.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def parse_token(token: str) -> CurrentUser:
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        expected_sig = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("bad signature")
        payload = json.loads(payload_bytes)
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        member_id = int(payload["sub"])
        role = str(payload["role"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token") from exc

    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/routes/auth.py:19-49] 密码哈希使用 SHA-256 单轮哈希，离线撞库成本过低 (CVSS: 8.1)
- 攻击向量：一旦数据库泄露，攻击者可对所有口令做高速字典/暴力破解，因为当前实现没有盐，也没有慢哈希参数，GPU/ASIC 能快速恢复弱口令。
- 影响：成员账号可被离线破解，进而获得 Bearer token 并横向访问活动、报名、签到和成员资料。
- 修复：改为 Argon2id 或 bcrypt，并为每个密码单独生成盐；登录时使用对应库的 verify 接口。
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


# register
password_hash = hash_password(payload.password)

# login
if not verify_password(payload.password, row["password_hash"]):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid phone or password")
```

### [backend/routes/announcements.py:18-50] 公告写接口允许未认证用户进入鉴权分支，授权设计不一致 (CVSS: 7.4)
- 攻击向量：`create_announcement_endpoint`、`patch_announcement`、`remove_announcement` 依赖 `get_optional_current_user`，然后再调用 `admin_or_leader`；这会把“未登录”和“权限不足”混在一起，外部调用者可反复试探公告管理接口行为并借助不同返回码区分认证状态。
- 影响：公告管理边界不稳定，容易在后续重构中被误用成真正的匿名写入入口；同时它与其他路由使用的强制认证模式不一致，扩大了权限绕过风险面。
- 修复：把写操作全部改成强制认证依赖，读取接口如果要匿名访问，应单独拆分匿名只读路由，不要用 optional current user 参与授权决策。
```python
from .common import CurrentUser, admin_or_leader, announcement_payload, get_current_user

@router.post('', response_model=ApiResponse, status_code=201)
def create_announcement_endpoint(
    payload: AnnouncementCreate = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    admin_or_leader(current_user)
    ...

@router.patch('/{announcement_id}', response_model=ApiResponse)
def patch_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    admin_or_leader(current_user)
    ...

@router.delete('/{announcement_id}', response_model=ApiResponse)
def remove_announcement(
    announcement_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    admin_or_leader(current_user)
    ...
```

## 中等 (CVSS 4-6)
### [backend/schemas.py:13-35] 成员输入对 phone 仅做长度校验，缺少语义格式约束 (CVSS: 5.6)
- 攻击向量：攻击者可提交包含空白、控制字符、非电话字符或奇异格式的 phone 值，绕过前端预期并污染成员主键业务语义；如果后续在日志、导出或搜索中使用该字段，还会放大数据污染问题。
- 影响：登录/注册/成员更新的身份标识会出现脏数据，导致重复账号、检索混乱和风控误判。
- 修复：对 phone 增加明确格式约束，必要时统一规范化为 E.164 或项目内固定格式，并在存储前做 strip/normalize。
```python
from pydantic import BaseModel, Field, field_validator
import re

PHONE_RE = re.compile(r"^\+?[0-9]{7,20}$")

class MemberBase(BaseModel):
    phone: Optional[str] = Field(default=None, min_length=7, max_length=20)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError("invalid phone format")
        return value
```

### [backend/routes/common.py:71-80] optional bearer 认证允许“匿名/认证”双态接口，增加授权误配概率 (CVSS: 4.8)
- 攻击向量：多个路由把 `get_optional_current_user` 作为依赖，随后由业务代码决定是否允许匿名或管理员行为；一旦后续新增路由复用该依赖，就很容易漏掉对 `None`、角色和身份的一致性检查。
- 影响：权限判断分散在各路由中，审计和维护成本增加，产生未来的授权绕过面。
- 修复：把 optional 认证仅限制在真正匿名可读的路由；任何写操作和权限边界路由都必须使用强制认证依赖，并在同一层完成授权判断。
```python
# 仅供匿名只读使用

def get_optional_current_user(...):
    ...

# 写接口统一改为：
current_user: CurrentUser = Depends(get_current_user)
```

## 低危 (CVSS < 4)
### [backend/routes/auth.py:19,42] 登录/注册继续使用 SHA-256 的痕迹暴露了密码方案过弱 (CVSS: 3.7)
- 攻击向量：即使没有数据库泄露，攻击者也可以假设口令校验为单轮哈希，从而对泄露的哈希做快速离线测试；弱口令账户被恢复的概率高于采用慢哈希时的基线。
- 影响：口令强度不足时，账号安全性明显下降。
- 修复：与严重项一致，统一迁移到 Argon2id/bcrypt，并为旧哈希做登录后升级。
```python
if is_legacy_sha256_hash(row["password_hash"]):
    if verify_legacy_sha256(payload.password, row["password_hash"]):
        new_hash = pwd_context.hash(payload.password)
        update_member_password(row["id"], new_hash)
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] 口令哈希是否已迁移到 Argon2id/bcrypt
- [ ] 登录失败与 token 失效是否统一返回 401
- [ ] 所有写接口是否使用强制认证依赖
