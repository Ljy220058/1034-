# 安全审计报告

审计对象：1034 跑团管理系统（FastAPI + SQLite）
审计日期：2026-06-06
审计范围：认证逻辑、授权中间件、输入验证、SQL 访问、密钥管理、敏感字段审计面板

## 严重 (CVSS >= 7)

### [backend/routes/common.py:50-71] JWT 令牌未签名，任意人可伪造身份与角色 (CVSS: 9.8)
- 攻击向量：令牌格式只是 `id:role:expires_at` 明文拼接；攻击者只要知道任意成员 id 与角色名，就能直接构造 Bearer token，无需掌握密钥，也无需破解签名。
- 影响：攻击者可伪装成任意现有用户，甚至伪装成 admin/leader 访问成员管理、工作区面板、任务健康接口；一旦组合角色提升漏洞，可横向读取所有敏感业务数据。
- 修复：
```python
# backend/routes/common.py
from datetime import timedelta, timezone
from jose import jwt, JWTError
import os

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = 'HS256'
TOKEN_TTL_HOURS = 7

def token_for_member(member: Member) -> str:
    payload = {
        'sub': str(member.id),
        'role': member.role,
        'exp': utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
        'iat': utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def parse_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        member_id = int(payload['sub'])
        role = payload['role']
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc
    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)
```

### [backend/routes/members.py:55-67] 普通成员可自助修改角色字段，存在角色提升路径 (CVSS: 8.8)
- 攻击向量：`PATCH /api/v1/members/{member_id}` 允许非 admin 用户提交 `role` 字段；代码在第 62-63 行把非 admin 的任意 role 强制改写为 `member`，但如果攻击者持有伪造 token（见上一个漏洞）或未来该分支被误用，角色检查与对象更新之间存在业务绕行风险。更关键的是，API 允许客户端传递角色字段本身，攻击面不应暴露。
- 影响：角色字段属于授权边界；一旦认证层或调用链出现差异化调用，攻击者可借助该入口把账号升级为 leader/admin，继而读取和修改全局数据。
- 修复：
```python
# backend/routes/members.py
@router.patch('/{member_id}', response_model=ApiResponse)
def patch_member(member_id: int, payload: MemberUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_write_guard(member_id, current_user)
    if current_user.role != ROLE_ADMIN and payload.role is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    if current_user.role != ROLE_ADMIN:
        payload = payload.model_copy(update={'role': None})
    member = update_member(member_id, payload)
    ...
```

### [backend/routes/workspaces.py:64-140] 管理面板接口可枚举并查询任意工作区任务状态，缺少资源级授权 (CVSS: 8.1)
- 攻击向量：只要通过任何方式取得 admin/leader 身份，攻击者即可在 `workspace_path` 参数中提交任意本地目录，查询该目录下的任务状态、工作区摘要、worker 建议与健康统计。`_safe_workspace_path` 只做路径形式约束，不验证该工作区是否属于当前用户可管理的资源域。
- 影响：泄露跨项目任务分布、运行状态、失败趋势、工作区绝对路径，辅助后续横向移动与社工；在共享主机上还会暴露目录结构与部署布局。
- 修复：
```python
# backend/routes/workspaces.py
from ..authorization import assert_workspace_access

@router.get('/workspaces/tasks/health', response_model=ApiResponse)
def read_workspace_task_health(...):
    admin_or_leader(current_user)
    safe_workspace_path = _safe_workspace_path(workspace_path)
    assert_workspace_access(current_user, safe_workspace_path)
    counts = _task_health_counts(safe_workspace_path)
    ...
```

## 中等 (CVSS 4-6)

### [backend/routes/auth.py:29-38, 55-68] 密码哈希使用单轮 SHA-256，缺少盐和慢哈希 (CVSS: 6.5)
- 攻击向量：攻击者一旦从数据库、备份、日志或供应链环境中获取 `password_hash`，可直接进行高速离线字典攻击；由于没有盐，碰撞与彩虹表命中效率更高。
- 影响：成员口令可被批量恢复，随后攻击者使用合法登录流程获取 Bearer token，再访问所有受保护接口。
- 修复：
```python
# backend/routes/auth.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['argon2'], deprecated='auto')

password_hash = pwd_context.hash(payload.password)
...
if not pwd_context.verify(payload.password, row['password_hash']):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
```

### [backend/routes/common.py:36-47] 首个注册用户可通过注册接口自举为管理员/领队 (CVSS: 5.9)
- 攻击向量：系统空库时，注册接口允许第一个用户携带非 member 角色；若部署初始化窗口、测试库回放、清库重建发生在生产路径，攻击者可抢先注册并占据高权限账号。
- 影响：初始管理员被攻击者控制后，整站数据与工作区面板立即暴露。
- 修复：
```python
# backend/routes/common.py
if payload.__class__.__name__ == 'UserRegister' and data.get('role') != ROLE_MEMBER:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='registration role must be member')
# 首个管理员通过离线初始化脚本或环境变量创建，不走公开注册接口
```

### [backend/routes/workspaces.py:17-38] 工作区路径仅做字符串级黑名单检查，边界不完整 (CVSS: 5.4)
- 攻击向量：`_safe_workspace_path` 仅拒绝 `..` 和隐藏目录名，未限制允许根目录、未禁止符号链接跳转、未校验 canonical path 与允许列表的关系。攻击者可借助符号链接、挂载点或合法外层目录访问非预期路径。
- 影响：可扩展到非授权工作区、共享目录或敏感挂载，放大工作区信息泄露面。
- 修复：
```python
# backend/routes/workspaces.py
ALLOWED_WORKSPACE_ROOT = Path('/root/autodl-tmp/projects/hermes-swarm-lab/workspaces').resolve()

def _safe_workspace_path(workspace_path: str) -> Path:
    path = Path(workspace_path.strip()).expanduser().resolve(strict=True)
    if ALLOWED_WORKSPACE_ROOT not in path.parents and path != ALLOWED_WORKSPACE_ROOT:
        raise HTTPException(status_code=422, detail='工作区路径不合法')
    return path
```

## 低危 (CVSS < 4)

### [backend/routes/common.py:74-77] Authorization 头仅接受严格 `Bearer ` 前缀，缺少更明确的错误细分与日志审计 (CVSS: 3.1)
- 攻击向量：攻击者可批量探测接口是否依赖认证，并通过差异化错误响应确认 Bearer 方案；虽然不能直接绕过认证，但会提升探测效率。
- 影响：增加枚举与调试便利性，降低攻击成本。
- 修复：
```python
# backend/routes/common.py
# 保持 401，但在服务端安全日志记录缺失/畸形 Authorization 的来源 IP、路径与用户代理
if not authorization or not authorization.startswith('Bearer '):
    audit_logger.info('auth header missing or malformed', extra={...})
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
```

### [backend/routes/auth.py:38-39, 67-68] 返回体包含 access_token 与完整 member 对象，缺少最小化输出约束 (CVSS: 3.7)
- 攻击向量：任何成功登录/注册响应都会同时返回令牌和成员字段；前端调试代理、浏览器扩展、日志采集器若记录响应体，会扩大 token 暴露面。
- 影响：访问令牌和个人信息更容易被误采集到日志、APM 或错误回传中。
- 修复：
```python
# backend/routes/auth.py
return ApiResponse(data={'access_token': token, 'token_type': 'Bearer'})
# 如需 member 信息，另开 /me 接口获取，避免在认证响应中重复下发
```

## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
- [ ] password hashing 是否使用 Argon2/bcrypt/scrypt，而不是单轮 SHA-256
- [ ] 生产环境是否禁用注册接口的高权限自举
- [ ] 工作区访问是否有资源级 allowlist

## 审计结论
- 已覆盖认证、授权、输入验证、SQL 访问、密钥管理与敏感字段面板。
- 发现 3 个严重/高风险问题、3 个中等问题、2 个低危改进点。
- 最优先修复顺序：先改 JWT 签名与失效策略，再收紧角色/工作区授权，最后替换密码哈希与完善审计日志。
