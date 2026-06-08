# 安全审计报告

## 严重 (CVSS >= 7)

### [backend/settings.py:125] 工作区附件/文档路径缺少统一安全校验会导致任意文件读取 (CVSS: 7.5)
- 攻击向量：已登录的管理或领队用户向工作区相关接口提交 `../outside.txt`、`../../etc/passwd` 或 `/etc/passwd` 形式的路径参数，服务端在读取附件、文档或按路径构建工作区数据前若直接 `resolve()` 或拼接路径，会访问工作区外文件。
- 影响：攻击者读取主机敏感文件、项目配置、数据库文件和任务工作区外的文档，造成凭据泄露与数据泄露。
- 修复：统一使用工作区路径白名单校验，拒绝穿越段、绝对越界路径和隐藏路径。
```python
from pathlib import Path

from backend.settings import WorkspaceBootstrapError, validate_workspace_access_path


def safe_document_path(user_path: str, workspace_root: Path) -> Path:
    try:
        path = validate_workspace_access_path(user_path, workspace_root=workspace_root)
    except WorkspaceBootstrapError as exc:
        raise HTTPException(status_code=422, detail='工作区路径不合法') from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail='文件不存在')
    return path
```

## 中等 (CVSS 4-6)

### [backend/routes/workspaces.py:41] 工作区 API 缺少恶意路径回归测试覆盖 (CVSS: 6.5)
- 攻击向量：攻击者对 `/api/v1/workspaces/board`、`/api/v1/workspaces/tasks/board`、`/api/v1/workspaces/tasks/diagnostics`、`/api/v1/workspaces/idle-worker-recommendations`、`/api/v1/workspaces/tasks/{task_id}/health` 反复提交穿越路径、绝对路径和隐藏文件路径；没有回归测试时，后续重构会重新引入越界访问。
- 影响：路径过滤在版本迭代中失效，附件/文档访问边界被绕过，敏感文件读取风险回归到生产环境。
- 修复：为所有接收 `workspace_path` 的 API 增加同一组恶意路径用例，并断言返回 422 与中文风险提示。
```python
def test_workspace_api_rejects_traversal_absolute_hidden_and_outside_paths(client, headers):
    for unsafe_path in ['../outside.txt', '../../etc/passwd', '/etc/passwd', '.env', 'docs/.secret.md']:
        response = client.get(
            '/api/v1/workspaces/tasks/board',
            params={'workspace_path': unsafe_path},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()['detail'] == '工作区路径不合法：禁止访问工作区外部、绝对路径或隐藏文件路径'
```

### [backend/settings.py:142] 隐藏文件路径未作为独立安全边界验证 (CVSS: 5.3)
- 攻击向量：攻击者提交 `.env`、`.git/config` 或 `docs/.secret.md` 等隐藏路径，绕过只检查 `..` 的过滤逻辑，读取部署密钥、Git 远端凭据或内部草稿文档。
- 影响：JWT secret、数据库连接串、API key、内部配置和未发布文档泄露。
- 修复：路径校验逐段拒绝隐藏文件和隐藏目录，并保留单元测试锁定该行为。
```python
raw_path = Path(user_path).expanduser()
relative_parts = raw_path.parts[1:] if raw_path.is_absolute() else raw_path.parts
if '..' in relative_parts or any(part.startswith('.') for part in relative_parts if part not in ('', '.', '..')):
    raise WorkspaceBootstrapError('refusing to access unsafe workspace path')
```

## 低危 (CVSS < 4)

### [backend/routes/workspaces.py:274] 工作区推荐接口缺少中文风险说明会降低运维可见性 (CVSS: 3.1)
- 攻击向量：安全边界触发后，调用方只能看到通用数据返回，不能在正常响应中确认路径访问策略；运维排查时会误判合法路径和非法路径的边界。
- 影响：安全策略不可见，测试和人工验收难以复现路径穿越、绝对路径、隐藏文件和非工作区访问四类边界。
- 修复：在工作区推荐响应中保留中文 `risk_note`，明确拒绝 `../`、`/etc/passwd`、隐藏路径和非工作区访问。
```python
return {
    'source': 'sqlite_workspace_snapshot',
    'risk_note': '路径参数已限制在工作区内，拒绝 ../、/etc/passwd、隐藏文件路径和非工作区文件访问，避免附件/文档路径穿越导致敏感文件泄露。',
}
```

## 密钥/配置检查
- [x] JWT secret 是否在环境变量中：本次变更未新增 JWT secret；附件/文档路径测试覆盖 `.env` 隐藏文件拒绝，降低 secret 文件被读风险。
- [x] 数据库连接串是否含明文密码：SQLite 路径通过 `RUNNING_CLUB_DB_PATH` 配置；本次变更未新增明文数据库密码。
- [x] .env 是否在 .gitignore：本次路径校验和回归测试将 `.env` 作为隐藏文件访问拒绝用例。

## 本次落地验证
- 新增 `tests/test_workspace_path_security.py`：覆盖路径穿越、绝对路径、隐藏路径、非工作区访问拒绝，以及合法工作区路径仍可访问。
- 扩展 `tests/test_workspace_inventory.py:131`：直接验证 `validate_workspace_access_path()` 对 `../`、`/etc/passwd`、`.env`、`docs/.hidden.md` 的拒绝行为。
- 执行命令：`python -m pytest tests/test_workspace_inventory.py tests/test_workspace_path_security.py`
- 结果：11 passed。
