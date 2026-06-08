from __future__ import annotations

from pathlib import Path


文档路径 = Path(__file__).resolve().parents[1] / 'docs' / 'running_data_import_wizard_smoke_checklist.md'


def _读取清单() -> str:
    return 文档路径.read_text(encoding='utf-8')


def test_冒烟清单_文件存在且全中文标题_可作为交付物() -> None:
    """冒烟清单必须位于 docs 目录并使用中文标题说明交付内容。"""
    # Arrange
    内容 = _读取清单()

    # Act
    首行 = 内容.splitlines()[0]

    # Assert
    assert 文档路径.exists()
    assert 首行 == '# 跑团导入向导冒烟测试清单'


def test_冒烟清单_四类导入入口_均被覆盖() -> None:
    """高驰、佳明、CSV/JSON 文件导入和手动录入四类入口都在清单中。"""
    # Arrange
    内容 = _读取清单()

    # Act
    入口关键词 = ['高驰', '佳明', 'CSV/JSON 文件导入', '手动录入']

    # Assert
    assert all(关键词 in 内容 for 关键词 in 入口关键词)


def test_冒烟清单_核心风险场景_均有检查项() -> None:
    """成功导入、缺少字段、重复活动、权限不足、异常配速和移动端提示均有检查项。"""
    # Arrange
    内容 = _读取清单()

    # Act
    风险关键词 = ['确认授权后只进入安全占位', '缺少必填字段', '重复活动', '权限不足', '异常配速', '移动端错误提示']

    # Assert
    assert all(关键词 in 内容 for 关键词 in 风险关键词)


def test_冒烟清单_检查项数量不少于十二条_满足验收下限() -> None:
    """清单至少提供 12 条可执行冒烟检查项。"""
    # Arrange
    内容 = _读取清单()

    # Act
    检查项数量 = 内容.count('### SMOKE-')

    # Assert
    assert 检查项数量 >= 12


def test_冒烟清单_每条检查项包含预期和定位_便于失败排查() -> None:
    """每条冒烟检查项都必须写明预期结果与失败定位入口。"""
    # Arrange
    内容 = _读取清单()

    # Act
    段落 = [段 for 段 in 内容.split('### SMOKE-')[1:]]

    # Assert
    assert all('预期结果：' in 段 for 段 in 段落)
    assert all('失败定位入口：' in 段 for 段 in 段落)


def test_冒烟清单_提供专项_pytest_命令_可快速执行() -> None:
    """清单提供不依赖外部网络的专项 pytest 冒烟命令。"""
    # Arrange
    内容 = _读取清单()

    # Act
    命令片段 = 'pytest -q tests/test_running_data_import_precheck.py tests/test_running_data_import_wizard.py'

    # Assert
    assert 命令片段 in 内容
    assert 'tests/test_running_data_import_smoke_checklist.py' in 内容
