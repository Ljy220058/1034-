from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / 'scripts' / 'scan-sensitive-info.py'


def _run_scan(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), str(target)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sensitive_info_scanner_detects_required_secret_patterns(tmp_path: Path) -> None:
    sample = tmp_path / 'leaky_config.py'
    sample.write_text(
        "\n".join(
            [
                "JWT_SECRET = '0123456789abcdef0123456789abcdef'",
                "API_TOKEN = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'",
                "DATABASE_URL = 'postgres://app:plainpass@db.local:5432/prod'",
                "print('debug user phone=13800000000 id_card=110101199001011234 email=runner@example.com')",
                "password = 'admin123456'",
            ]
        ),
        encoding='utf-8',
    )

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    output = result.stdout
    assert '硬编码密钥' in output
    assert '测试令牌' in output
    assert '配置明文凭据' in output
    assert '调试日志个人信息' in output
    assert '明文密码' in output
    assert '风险说明' in output
    assert '误报处理建议' in output


def test_sensitive_info_scanner_allows_legitimate_examples(tmp_path: Path) -> None:
    sample = tmp_path / 'safe_examples.py'
    sample.write_text(
        "\n".join(
            [
                "JWT_SECRET = os.environ['JWT_SECRET']",
                "RUNNING_CLUB_DB_PATH = './data/running_club.db'",
                "logger.info('用户登录成功，member_id=%s', member_id)",
                "password_hash = hash_password(password)",
                "api_key = os.getenv('PAYMENT_API_KEY')",
            ]
        ),
        encoding='utf-8',
    )

    result = _run_scan(tmp_path)

    assert result.returncode == 0
    assert '未发现敏感信息泄露命中' in result.stdout


def test_sensitive_info_scanner_respects_allowlist_comments(tmp_path: Path) -> None:
    sample = tmp_path / 'fixtures.py'
    sample.write_text(
        "API_TOKEN = 'test_token_for_docs_only_1234567890'  # pragma: allow-sensitive 示例占位值\n",
        encoding='utf-8',
    )

    result = _run_scan(tmp_path)

    assert result.returncode == 0
    assert '未发现敏感信息泄露命中' in result.stdout
