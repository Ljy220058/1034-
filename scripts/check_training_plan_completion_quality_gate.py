from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import connect, DB_PATH


@dataclass(frozen=True)
class TrainingPlanCompletionRecord:
    """训练计划完成率门禁检查结果。"""

    plan_id: str
    plan_name: str
    start_date: date
    end_date: date
    target_days: int
    checked_in_days: int
    make_up_days: int
    completion_rate: float
    status: str
    reason: str


@dataclass(frozen=True)
class QualityGateRuleResult:
    """单条自动化检查规则的执行结果。"""

    rule_id: str
    passed: bool
    title: str
    detail: str


DEFAULT_MIN_COMPLETION_RATE = 0.8
DATE_FORMAT = '%Y-%m-%d'


def _parse_date(value: str) -> date:
    """解析 ISO 日期字符串。"""
    return datetime.strptime(value, DATE_FORMAT).date()


def _get_first_row(connection, sql: str, params: Sequence[object]) -> object | None:
    """执行查询并返回首行。"""
    cursor = connection.execute(sql, params)
    return cursor.fetchone()


def _fetch_training_plans(db_path: Path) -> list[TrainingPlanCompletionRecord]:
    """读取训练计划完成率相关数据。"""
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                p.id AS plan_id,
                p.name AS plan_name,
                p.start_date,
                p.end_date,
                COALESCE(p.target_days, 0) AS target_days,
                COALESCE(SUM(CASE WHEN r.attendance_status = 'signed_in' THEN 1 ELSE 0 END), 0) AS checked_in_days,
                COALESCE(SUM(CASE WHEN r.attendance_status = 'make_up' THEN 1 ELSE 0 END), 0) AS make_up_days,
                COALESCE(MAX(CASE WHEN r.attendance_status IN ('signed_in', 'make_up') THEN 1 ELSE 0 END), 0) AS has_activity
            FROM training_plans p
            LEFT JOIN training_plan_records r ON r.plan_id = p.id
            GROUP BY p.id, p.name, p.start_date, p.end_date, p.target_days
            ORDER BY p.start_date ASC, p.id ASC
            """
        ).fetchall()

    plans: list[TrainingPlanCompletionRecord] = []
    for row in rows:
        start = _parse_date(str(row['start_date']))
        end = _parse_date(str(row['end_date']))
        target_days = int(row['target_days'])
        checked_in_days = int(row['checked_in_days'])
        make_up_days = int(row['make_up_days'])
        completed_days = checked_in_days + make_up_days
        completion_rate = (completed_days / target_days) if target_days else 0.0
        status = 'pass' if completion_rate >= DEFAULT_MIN_COMPLETION_RATE else 'fail'
        reason = '完成率达标' if status == 'pass' else '完成率未达到门禁阈值'
        if not int(row['has_activity']):
            reason = '缺少打卡记录'
            status = 'fail'
        plans.append(
            TrainingPlanCompletionRecord(
                plan_id=str(row['plan_id']),
                plan_name=str(row['plan_name']),
                start_date=start,
                end_date=end,
                target_days=target_days,
                checked_in_days=checked_in_days,
                make_up_days=make_up_days,
                completion_rate=completion_rate,
                status=status,
                reason=reason,
            )
        )
    return plans


def _rule_cross_month_boundary(start: date, end: date) -> QualityGateRuleResult:
    """检查训练计划是否跨月。"""
    passed = start.month == end.month and start.year == end.year
    detail = '计划跨月' if not passed else '计划未跨月'
    return QualityGateRuleResult('cross_month_boundary', passed, '跨月边界检查', detail)


def _rule_leap_day(start: date, end: date) -> QualityGateRuleResult:
    """检查训练计划是否覆盖闰日。"""
    leap_day = date(start.year, 2, 29) if start.year % 4 == 0 else None
    passed = leap_day is None or not (start <= leap_day <= end)
    detail = '计划覆盖闰日' if not passed else '未覆盖闰日'
    return QualityGateRuleResult('leap_day', passed, '闰日检查', detail)


def _rule_duplicate_checkins(records: Sequence[TrainingPlanCompletionRecord]) -> QualityGateRuleResult:
    """检查是否存在重复打卡。"""
    repeated = any(record.checked_in_days > record.target_days for record in records)
    return QualityGateRuleResult('duplicate_checkins', not repeated, '重复打卡检查', '存在重复打卡' if repeated else '未发现重复打卡')


def _rule_missing_target(records: Sequence[TrainingPlanCompletionRecord]) -> QualityGateRuleResult:
    """检查是否存在缺失目标。"""
    missing = any(record.target_days <= 0 for record in records)
    return QualityGateRuleResult('missing_target', not missing, '缺失目标检查', '存在缺失目标' if missing else '目标完整')


def _rule_over_completion(records: Sequence[TrainingPlanCompletionRecord]) -> QualityGateRuleResult:
    """检查完成率是否超过 100%。"""
    overflow = any(record.completion_rate > 1.0 for record in records)
    return QualityGateRuleResult('over_completion', not overflow, '完成率上限检查', '完成率超过 100%' if overflow else '完成率未超上限')


def _rule_message_consistency(records: Sequence[TrainingPlanCompletionRecord]) -> QualityGateRuleResult:
    """检查中文错误提示是否统一。"""
    allowed_messages = {'缺少打卡记录', '完成率未达到门禁阈值'}
    inconsistent = any(record.reason not in allowed_messages for record in records if record.status == 'fail')
    return QualityGateRuleResult('message_consistency', not inconsistent, '中文提示一致性检查', '中文错误提示不一致' if inconsistent else '中文错误提示一致')


def run_training_plan_completion_quality_gate(db_path: Path | None = None) -> dict[str, object]:
    """运行训练计划完成率质量门禁检查。"""
    path = db_path or DB_PATH
    plans = _fetch_training_plans(path)
    if not plans:
        return {
            'passed': False,
            'summary': '未找到训练计划数据，无法执行完成率门禁。',
            'records': [],
            'rules': [],
        }

    rules: list[QualityGateRuleResult] = []
    first = plans[0]
    rules.append(_rule_cross_month_boundary(first.start_date, first.end_date))
    rules.append(_rule_leap_day(first.start_date, first.end_date))
    rules.append(_rule_duplicate_checkins(plans))
    rules.append(_rule_missing_target(plans))
    rules.append(_rule_over_completion(plans))
    rules.append(_rule_message_consistency(plans))

    passed = all(rule.passed for rule in rules)
    return {
        'passed': passed,
        'summary': '训练计划完成率质量门禁通过' if passed else '训练计划完成率质量门禁失败',
        'records': [record.__dict__ for record in plans],
        'rules': [rule.__dict__ for rule in rules],
    }


def format_quality_gate_report(result: dict[str, object]) -> str:
    """把门禁结果格式化为可读文本。"""
    lines = [f"结果：{'通过' if result.get('passed') else '失败'}", f"摘要：{result.get('summary', '')}"]
    for rule in result.get('rules', []):
        if isinstance(rule, dict):
            lines.append(f"- {rule.get('rule_id')}: {'通过' if rule.get('passed') else '失败'}，{rule.get('detail', '')}")
    return '\n'.join(lines)
