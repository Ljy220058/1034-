# 安全审计报告
## 严重 (CVSS >= 7)
### [backend/seed_data.py:27-67] 预置固定 password_hash 明文占位符导致种子账号可预测 (CVSS: 8.1)
- 攻击向量：攻击者读取代码或导出的 seed pack 后，直接获知所有预置成员的密码哈希占位符；如果这些占位符在加载种子时被当作真实口令材料写入数据库，攻击者可用已知固定值针对预置账号做离线撞库或直接复用已知初始凭据进入系统。
- 影响：预置管理员/leader/member 账号的初始认证边界失效，攻击者可接管测试或演示环境中的高权限身份，并借此修改成员、活动、公告与报名记录。
- 修复：
```python
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
import json

try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover
    CryptContext = None

_PWD_CONTEXT = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto") if CryptContext else None


def _seed_password(label: str) -> str:
    secret = os.getenv("RUNNING_CLUB_SEED_SECRET")
    if secret:
        return _PWD_CONTEXT.hash(f"{secret}:{label}") if _PWD_CONTEXT else f"{secret}:{label}"
    if _PWD_CONTEXT:
        return _PWD_CONTEXT.hash(f"seed:{label}")
    raise RuntimeError("RUNNING_CLUB_SEED_SECRET is required when passlib is unavailable")


def build_seed_pack() -> SeedPack:
    members = [
        {
            "name": "Li Ming",
            "phone": "15550010001",
            "role": "leader",
            "running_years": 8,
            "pace": "5:10/km",
            "usual_distance_km": 12.0,
            "training_goal": "Lead the Tuesday tempo group",
            "password_hash": _seed_password("leader"),
        },
        # repeat for the remaining seed members
    ]
```
### [backend/seed_data.py:26-68] 种子包对认证材料没有参数化控制，测试/生产环境无法安全分离 (CVSS: 7.4)
- 攻击向量：攻击者或内部人员在不同环境中复用同一份种子数据，利用固定的预置认证材料在本地、测试或演示环境中获得可重复的登录入口，然后横向寻找被错误同步到准生产环境的同一口令材料。
- 影响：种子数据在多个环境间可被无差别复用，导致测试凭据进入共享环境后被长期保留，增加账号接管与越权风险。
- 修复：
```python
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class SeedPack:
    members: list[dict[str, object]]
    activities: list[dict[str, object]]
    registrations: list[dict[str, object]]
    attendances: list[dict[str, object]]
    announcements: list[dict[str, object]]


def build_seed_pack(password_hasher: Callable[[str], str] | None = None) -> SeedPack:
    password_hasher = password_hasher or (lambda label: _seed_password(label))
    members = [
        {
            "name": "Li Ming",
            # ...
            "password_hash": password_hasher("leader"),
        },
    ]
    return SeedPack(members, activities, registrations, attendances, announcements)


def build_test_seed_pack() -> SeedPack:
    return build_seed_pack(password_hasher=lambda label: f"test-hash:{label}")
```
## 中等 (CVSS 4-6)
### [tests/test_seed_data.py:9-50] 仅测试确定性，没有断言 password_hash 不再是固定占位符 (CVSS: 5.4)
- 攻击向量：攻击者借助回归缺口，让固定占位符在后续提交中再次出现而不被测试发现，继续维持可预测的种子认证材料。
- 影响：安全修复很容易被回退，种子账号仍可被预期化利用，审计和上线验证失去约束力。
- 修复：
```python
def test_build_seed_pack_uses_parameterized_password_hashes() -> None:
    pack = build_seed_pack(password_hasher=lambda label: f"test-hash:{label}")

    assert [member["password_hash"] for member in pack.members] == [
        "test-hash:leader",
        "test-hash:admin",
        "test-hash:member-a",
        "test-hash:member-b",
    ]
    assert all(not str(member["password_hash"]).startswith("seeded-password-hash") for member in pack.members)
```
### [scripts/generate_seed_pack.py:8-?] 生成脚本未显式注入种子密钥，默认运行时行为不透明 (CVSS: 4.8)
- 攻击向量：攻击者或误操作人员在不同机器上执行种子生成脚本时，因缺少明确的密钥参数化策略而落入默认值路径，生成可预测或不一致的口令材料并传播到数据库或导出文件。
- 影响：种子生成结果无法稳定审计，测试数据可能与预期不一致，增加将弱凭据带入共享环境的概率。
- 修复：
```python
import os
from backend.seed_data import build_seed_pack, export_seed_pack

if __name__ == "__main__":
    if not os.getenv("RUNNING_CLUB_SEED_SECRET"):
        raise SystemExit("RUNNING_CLUB_SEED_SECRET must be set for seed generation")
    export_seed_pack("/tmp/seed-pack.json")
```
## 低危 (CVSS < 4)
### [backend/seed_data.py:134-160] 种子导出/遍历接口未对敏感字段做最小化输出 (CVSS: 3.5)
- 攻击向量：攻击者若能读取导出的 seed pack 文件，可直接枚举全部预置成员、报名与签到关系，辅助社工与口令猜测。
- 影响：增加信息暴露面，帮助攻击者锁定高价值账号与业务关系。
- 修复：
```python
def export_seed_pack(target_path: str | Path) -> Path:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pack = build_seed_pack()
    payload = {
        "members": [{k: v for k, v in row.items() if k != "password_hash"} for row in pack.members],
        "activities": pack.activities,
        "registrations": pack.registrations,
        "attendances": pack.attendances,
        "announcements": pack.announcements,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
```
## 密钥/配置检查
- [ ] JWT secret 是否在环境变量中
- [ ] 数据库连接串是否含明文密码
- [ ] .env 是否在 .gitignore
