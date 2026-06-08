from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ImportErrorCopyRule:
    """跑步数据导入错误文案规则。

    Args:
        category: 错误场景分类。
        expected_message: 推荐使用的统一中文文案。
        suggestion: 给调用方或运营同学的处理建议。
        sources: 适用的数据来源展示名。
    """

    category: str
    expected_message: str
    suggestion: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class ImportErrorCopySample:
    """待检查的错误文案样本。

    Args:
        location: 文案所在位置，便于修复。
        category: 错误场景分类。
        message: 当前实际文案。
    """

    location: str
    category: str
    message: str


@dataclass(frozen=True)
class ImportErrorCopyIssue:
    """错误文案不一致项。

    Args:
        location: 文案所在位置。
        category: 错误场景分类。
        actual_message: 当前实际文案。
        expected_message: 推荐统一文案。
        suggestion: 修复建议。
    """

    location: str
    category: str
    actual_message: str
    expected_message: str
    suggestion: str


@dataclass(frozen=True)
class ImportErrorCopyReport:
    """错误文案检查结果。

    Args:
        total_checked: 已检查样本数。
        inconsistencies: 不一致项列表。
    """

    total_checked: int
    inconsistencies: list[ImportErrorCopyIssue]


_RULES: tuple[ImportErrorCopyRule, ...] = (
    ImportErrorCopyRule(
        category='缺少字段',
        expected_message='导入数据缺少必填字段，请补齐后重试',
        suggestion='补齐活动名称、开始时间、距离或运动时长等必填字段。',
        sources=('高驰', '佳明', '通用 CSV/JSON'),
    ),
    ImportErrorCopyRule(
        category='格式错误',
        expected_message='文件内容格式错误，请检查 CSV/JSON 后重试',
        suggestion='确认 CSV 首行是表头，JSON 内容为活动对象或活动列表。',
        sources=('高驰', '佳明', '通用 CSV/JSON'),
    ),
    ImportErrorCopyRule(
        category='内容不一致',
        expected_message='导入内容与当前页面配置不一致，请重新选择来源平台',
        suggestion='重新检查来源平台、文件格式和页面中的导入配置是否一致。',
        sources=('高驰', '佳明', '通用 CSV/JSON'),
    ),
    ImportErrorCopyRule(
        category='重复活动',
        expected_message='活动已存在，请确认是否跳过重复记录',
        suggestion='按活动名称和开始时间核对重复记录，确认后再继续导入。',
        sources=('高驰', '佳明', '通用 CSV/JSON'),
    ),
    ImportErrorCopyRule(
        category='权限不足',
        expected_message='请先确认导入授权范围后再继续',
        suggestion='返回导入预检页，确认授权范围和隐私边界。',
        sources=('高驰', '佳明'),
    ),
    ImportErrorCopyRule(
        category='来源平台不支持',
        expected_message='暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON',
        suggestion='把来源平台改为 coros、garmin、generic 或 manual_file。',
        sources=('高驰', '佳明', '通用 CSV/JSON'),
    ),
)


def get_import_error_rules() -> tuple[ImportErrorCopyRule, ...]:
    """返回跑步数据导入错误文案规则表。

    Returns:
        不可变规则元组，覆盖五类中文错误场景。
    """
    return _RULES


def _normalize_message(value: str) -> str:
    """归一化待比较文案。

    Args:
        value: 原始文案。
    Returns:
        去除首尾空白后的文案。
    """
    return ' '.join(value.strip().split())


def _rule_by_category() -> dict[str, ImportErrorCopyRule]:
    """按分类索引规则表。

    Returns:
        分类到规则的映射。
    """
    return {rule.category: rule for rule in _RULES}


def _coerce_sample(raw: ImportErrorCopySample | Mapping[str, object]) -> ImportErrorCopySample:
    """把字典样本转换为检查器内部样本。

    Args:
        raw: 样本对象或包含 location/category/message 的映射。
    Returns:
        规范化后的样本对象。
    """
    if isinstance(raw, ImportErrorCopySample):
        return raw
    return ImportErrorCopySample(
        location=str(raw.get('location', '未命名位置')),
        category=str(raw.get('category', '')),
        message=str(raw.get('message', '')),
    )


def check_import_error_messages(samples: Sequence[ImportErrorCopySample | Mapping[str, object]]) -> ImportErrorCopyReport:
    """检查导入错误文案是否符合中文规则表。

    Args:
        samples: 待检查文案样本列表。
    Returns:
        包含不一致项和建议文案的检查结果。
    """
    rules = _rule_by_category()
    issues: list[ImportErrorCopyIssue] = []
    for raw_sample in samples:
        sample = _coerce_sample(raw_sample)
        rule = rules.get(sample.category)
        if rule is None:
            issues.append(
                ImportErrorCopyIssue(
                    location=sample.location,
                    category=sample.category or '未分类',
                    actual_message=sample.message,
                    expected_message='请先补充该错误场景的中文规则',
                    suggestion='把该场景纳入规则表后再统一文案。',
                )
            )
            continue
        if _normalize_message(sample.message) != _normalize_message(rule.expected_message):
            issues.append(
                ImportErrorCopyIssue(
                    location=sample.location,
                    category=sample.category,
                    actual_message=sample.message,
                    expected_message=rule.expected_message,
                    suggestion=rule.suggestion,
                )
            )
    return ImportErrorCopyReport(total_checked=len(samples), inconsistencies=issues)


def format_import_error_report(report: ImportErrorCopyReport) -> str:
    """把检查结果格式化为稳定中文输出。

    Args:
        report: 文案检查结果。
    Returns:
        适合 CLI 或测试断言的中文报告。
    """
    if not report.inconsistencies:
        return f'检查完成：{report.total_checked} 项文案一致，未发现不一致。'

    lines = [f'发现 {len(report.inconsistencies)} 项导入错误文案不一致，共检查 {report.total_checked} 项。']
    for index, issue in enumerate(report.inconsistencies, start=1):
        lines.extend(
            [
                f'第 {index} 项：{issue.location}',
                f'场景：{issue.category}',
                f'当前文案：{issue.actual_message}',
                f'建议改为：{issue.expected_message}',
                f'处理建议：{issue.suggestion}',
            ]
        )
    return '\n'.join(lines)
