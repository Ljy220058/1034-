# 安全审计报告

审计对象：1034 跑团管理系统（FastAPI + SQLite）
审计日期：2026-06-06
审计范围：backend/routes/common.py、backend/routes/auth.py、backend/routes/members.py、backend/routes/activities.py、backend/routes/announcements.py、backend/routes/checkins.py、backend/routes/workspaces.py、backend/models.py、backend/database.py、backend/settings.py、backend/repository.py、tests/test_auth.py、requirements.txt

## 严重 (CVSS >= 7)
### [backend/routes/common.py:47-68, backend/routes/auth.py:17-31, backend/routes/auth.py:34-49] 认证令牌未签名，且角色/过期时间仅由客户端可改写 (CVSS: 9.8)
- 攻击向量：攻击者只要拿到任意有效 token，就可以直接修改 token 字符串中的 member_id、role 或 expires_at 字段；服务端仅按“id:role:expires_at”拆分并解析，没有任何 HMAC/JWT 签名校验，也没有服务器端会话状态约束。攻击者可把普通成员 token 改成 admin/leader，并把过期时间改到未来，从而伪造高权限身份长期访问。
- 影响：认证、授权全部失效；成员管理、活动管理、公告发布、考勤管理、任务队列等受保护接口都可能被直接接管，属于全局性权限提升。
- 修复：
```python
# backend/routes/common.py
import base64
import hashlib
import hmac
import json
import os

TOKEN_SECRET = os.getenv('RUNNING_CLUB_TOKEN_SECRET')
if not TOKEN_SECRET:
    raise RuntimeError('RUNNING_CLUB_TOKEN_SECRET is required')


def _sign_token(payload: dict[str, object]) -> str:
    body = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    sig = hmac.new(TOKEN_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body).decode('ascii').rstrip('=') + '.' + base64.urlsafe_b64encode(sig).decode('ascii').rstrip('=')


def _verify_token(token: str) -> dict[str, object]:
    try:
        body_b64, sig_b64 = token.split('.', 1)
        body = base64.urlsafe_b64decode(body_b64 + '==')
        sig = base64.urlsafe_b64decode(sig_b64 + '==')
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    expected = hmac.new(TOKEN_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return json.loads(body)


def token_for_member(member: Member) -> str:
    payload = {
        'sub': member.id,
        'role': member.role,
        'exp': int((utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    return _sign_token(payload)


def parse_token(token: str) -> CurrentUser:
    payload = _verify_token(token)
    ...
```

### [backend/routes/common.py:71-80, backend/routes/members.py:22-26, backend/routes/announcements.py:12-23, backend/routes/activities.py:12-24, backend/routes/checkins.py:22-43, backend/routes/workspaces.py:127-152, backend/routes/workspaces.py:155-265] 多个受保护路由对认证依赖不一致，存在可被绕过的公开面 (CVSS: 8.1)
- 攻击向量：系统中同时存在强制 `Depends(get_current_user)`、可空 `get_optional_current_user`、以及少量直接依赖角色值的混用模式。攻击者只需寻找遗漏认证的接口，就能绕过统一鉴权入口直接调用高危变更操作；例如某些接口只做角色断言而没有强制校验 token，或者把“可空用户”传入后再走角色分支，容易出现未来补丁引入的空认证绕过。
- 影响：任何新增或回归的管理接口都可能在未登录状态下被调用；一旦后续改动复制了当前模式，攻击面会快速扩大到成员、公告、任务队列等管理能力。
- 修复：
```python
# backend/routes/common.py
from fastapi import Depends

def require_authenticated(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


def require_admin_or_leader(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role not in {ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    return current_user

# backend/routes/announcements.py
@router.post('', response_model=ApiResponse, status_code=201)
def create_announcement_endpoint(
    payload: AnnouncementCreate = Body(...),
    current_user: CurrentUser = Depends(require_admin_or_leader),
) -> ApiResponse:
    ...
```

## 中等 (CVSS 4-6)
### [backend/routes/auth.py:19-19, tests/test_auth.py:30-74] 密码使用 SHA-256 直接哈希，缺少慢哈希和逐用户盐 (CVSS: 6.5)
- 攻击向量：攻击者若拿到数据库文件、备份、日志或任意导出数据，就能对 `password_hash` 做高速离线穷举。SHA-256 适合完整性校验，不适合口令存储；缺少 salt 和工作因子会显著降低破解成本，常见弱口令可被批量恢复。
- 影响：成员账号可被离线恢复，随后配合 token 伪造或正常登录拿到系统访问权；一旦有管理员账号泄露，所有管理接口都受影响。
- 修复：
```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# register/login 中替换 hashlib.sha256 + compare_digest
password_hash = _hash_password(payload.password)
if not _verify_password(payload.password, row['password_hash']):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```

### [backend/routes/common.py:36-44, backend/routes/members.py:54-66] 角色字段在更新路径上由业务层回写，缺少统一的角色变更策略 (CVSS: 5.9)
- 攻击向量：当前实现通过“先允许输入 role，再在业务层把非管理员强制改回 member”的方式实现角色约束。这个逻辑分散在多个分支里，后续新增更新路径、批量导入路径或其他写接口时，很容易遗漏同样的回写，导致普通用户通过新入口提交 role 字段并获得权限提升。
- 影响：一旦某个变更接口复用了 `MemberUpdate` 而没有沿用当前回写逻辑，就会出现角色提升；这类缺陷通常在新增接口后才暴露，风险持续存在。
- 修复：
```python
# backend/models.py
class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)
    # remove role from self-service update model

# backend/routes/members.py
if current_user.role != ROLE_ADMIN and 'role' in payload.model_fields_set:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
```

### [backend/database.py:10-11, backend/settings.py:9-10, backend/app.py:183-190] 数据库路径默认落到临时目录，生产环境容易被共享/覆写 (CVSS: 4.8)
- 攻击向量：如果部署时未显式设置 `RUNNING_CLUB_DB_PATH`，数据库会落到系统临时目录下的固定文件名。多进程、共享主机或容器复用环境里，攻击者或其他进程可利用路径可预测性进行覆写、替换或读取，导致数据污染或敏感数据暴露。
- 影响：成员、活动、公告和考勤数据可能被其他本地主体篡改；在错误部署场景下，应用重启后还可能意外接管到被预置的数据库文件。
- 修复：
```python
# backend/settings.py / backend/database.py
from pathlib import Path
import os

DB_PATH = Path(os.environ['RUNNING_CLUB_DB_PATH'])  # 强制生产配置显式提供
if not DB_PATH.is_absolute():
    raise RuntimeError('RUNNING_CLUB_DB_PATH must be absolute')
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
```

## 低危 (CVSS < 4)
### [backend/routes/common.py:36-44] 输入净化依赖类名字符串，缺少显式模式约束 (CVSS: 3.7)
- 攻击向量：`sanitize_member_payload()` 通过 `payload.__class__.__name__ == 'UserRegister'` 判断注册路径，属于脆弱的运行时类型字符串判断。未来如果引入子类、包装类或测试替身，这个判断可能失效，导致角色约束逻辑偏离预期。
- 影响：当前版本主要是可维护性和回归风险；在后续重构中可能放大为权限绕过。
- 修复：
```python
from typing import Type


def sanitize_member_payload(payload: MemberCreate | UserRegister, *, is_register: bool) -> dict[str, object]:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    if data.get('role') != ROLE_MEMBER and is_register:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')
    ...
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] 认证 token 是否具备签名校验
- [ ] 是否存在服务端可撤销的会话/令牌策略
- [ ] 是否对管理员接口强制统一鉴权依赖

## 审计结论
- 认证：存在严重缺陷，token 完全可伪造，必须优先修复。
- 授权：当前有角色守卫，但鉴权入口不统一，需收敛到单一依赖。
- 输入验证：Pydantic 约束整体较好，但角色和路径类输入仍需进一步收紧。
- SQL 注入：当前代码主要使用参数化查询，未发现直接字符串拼接 SQL 注入点。
- 密钥管理：未见 JWT secret 管理，token 也未签名，属于高风险设计缺陷。
