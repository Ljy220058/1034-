from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import connect
from ..models import ApiResponse
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/achievements', tags=['achievements'])


@dataclass(frozen=True)
class AchievementRule:
    """成就规则定义。"""

    key: str
    name: str
    description: str
    threshold_type: str
    threshold_value: float

    def as_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'threshold': {'type': self.threshold_type, 'value': self.threshold_value},
        }


RULES: tuple[AchievementRule, ...] = (
    AchievementRule('rookie_runner', '入门跑者', '累计跑量达到 10 公里', 'total_distance_km', 10),
    AchievementRule('streak_star', '坚持之星', '连续打卡达到 7 天', 'streak_days', 7),
    AchievementRule('monthly_perfect', '月度全勤', '本月打卡达到 20 天', 'monthly_checkin_days', 20),
    AchievementRule('distance_master', '里程达人', '累计跑量达到 100 公里', 'total_distance_km', 100),
    AchievementRule('speed_pioneer', '速度先锋', '单次最快配速达到 5:00/km 或更快', 'best_pace_seconds_per_km', 300),
    AchievementRule('social_runner', '社交达人', '参与活动达到 10 次', 'activity_participations', 10),
    AchievementRule('early_member', '早期成员', '注册时长达到 365 天', 'member_age_days', 365),
)


def _safe_int(value: Any) -> int:
    """安全转换为整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    """安全转换为浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_member_month() -> tuple[str, str]:
    """获取当前月份起止日期文本。"""
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start.isoformat(), end.isoformat()


def _calculate_streak_days(member_id: int) -> int:
    """计算连续打卡天数。"""
    with connect() as connection:
        rows = connection.execute(
            'SELECT DISTINCT DATE(COALESCE(signed_in_at, created_at)) AS checkin_date '
            "FROM attendances WHERE member_id = ? AND status = 'signed_in' ORDER BY checkin_date DESC",
            (member_id,),
        ).fetchall()
    if not rows:
        return 0
    dates = [datetime.strptime(str(row['checkin_date']), '%Y-%m-%d').date() for row in rows if row['checkin_date']]
    if not dates:
        return 0
    streak = 1
    expected = dates[0] - timedelta(days=1)
    for checkin_date in dates[1:]:
        if checkin_date == expected:
            streak += 1
            expected -= timedelta(days=1)
            continue
        break
    return streak


def _load_member_statistics(member_id: int) -> dict[str, Any]:
    """加载成员成就计算所需统计数据。"""
    month_start, month_end = _parse_member_month()
    with connect() as connection:
        member = connection.execute(
            'SELECT id, name, created_at FROM members WHERE id = ?',
            (member_id,),
        ).fetchone()
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
        stats = connection.execute(
            (
                'SELECT '
                'COALESCE(SUM(COALESCE(a.distance_km, 0)), 0) AS total_distance_km, '
                'COUNT(DISTINCT CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= ? '
                'AND DATE(COALESCE(at.signed_in_at, at.created_at)) < ? '
                'THEN DATE(COALESCE(at.signed_in_at, at.created_at)) END) AS monthly_checkin_days, '
                "COUNT(DISTINCT CASE WHEN at.status = 'signed_in' THEN at.activity_id END) AS activity_participations, "
                "MIN(CASE WHEN at.status = 'signed_in' AND a.distance_km IS NOT NULL AND a.distance_km > 0 "
                "THEN ROUND((julianday(COALESCE(at.signed_in_at, at.created_at)) - julianday(m.created_at)) * 24 * 60 * 60) END) AS best_pace_seconds_per_km "
                'FROM members m '
                "LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in' "
                'LEFT JOIN activities a ON a.id = at.activity_id '
                'WHERE m.id = ?'
            ),
            (month_start, month_end, member_id),
        ).fetchone()
    created_at = datetime.fromisoformat(str(member['created_at']).replace('Z', '+00:00'))
    return {
        'member_id': _safe_int(member['id']),
        'member_name': str(member['name'] or ''),
        'member_age_days': max(0, (datetime.now(timezone.utc) - created_at).days),
        'total_distance_km': _safe_float(stats['total_distance_km']),
        'monthly_checkin_days': _safe_int(stats['monthly_checkin_days']),
        'activity_participations': _safe_int(stats['activity_participations']),
        'best_pace_seconds_per_km': _safe_int(stats['best_pace_seconds_per_km']),
        'streak_days': _calculate_streak_days(member_id),
    }


def _evaluate_rules(stats: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """评估已获得与未获得成就。"""
    earned: list[dict[str, Any]] = []
    locked: list[dict[str, Any]] = []
    for rule in RULES:
        if rule.threshold_type == 'total_distance_km':
            passed = stats['total_distance_km'] >= rule.threshold_value
        elif rule.threshold_type == 'streak_days':
            passed = stats['streak_days'] >= rule.threshold_value
        elif rule.threshold_type == 'monthly_checkin_days':
            passed = stats['monthly_checkin_days'] >= rule.threshold_value
        elif rule.threshold_type == 'best_pace_seconds_per_km':
            passed = 0 < stats['best_pace_seconds_per_km'] <= rule.threshold_value
        elif rule.threshold_type == 'activity_participations':
            passed = stats['activity_participations'] >= rule.threshold_value
        elif rule.threshold_type == 'member_age_days':
            passed = stats['member_age_days'] >= rule.threshold_value
        else:
            passed = False
        payload = rule.as_dict()
        payload['earned'] = passed
        payload['progress'] = {'current': stats.get(rule.threshold_type, 0), 'target': rule.threshold_value}
        if passed:
            earned.append(payload)
        else:
            locked.append(payload)
    return earned, locked


def _leaderboard_rows() -> list[dict[str, Any]]:
    """按成就数量统计成员排行。"""
    with connect() as connection:
        rows = connection.execute(
            (
                'SELECT m.id AS member_id, m.name AS member_name, m.created_at, '
                'COALESCE(SUM(COALESCE(a.distance_km, 0)), 0) AS total_distance_km, '
                "COUNT(DISTINCT CASE WHEN at.status = 'signed_in' THEN at.activity_id END) AS activity_participations, "
                "COUNT(DISTINCT CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= DATE('now', 'start of month') "
                "AND DATE(COALESCE(at.signed_in_at, at.created_at)) < DATE('now', 'start of month', '1 month') "
                'THEN DATE(COALESCE(at.signed_in_at, at.created_at)) END) AS monthly_checkin_days '
                'FROM members m '
                "LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in' "
                'LEFT JOIN activities a ON a.id = at.activity_id '
                'GROUP BY m.id, m.name, m.created_at '
                'ORDER BY total_distance_km DESC, activity_participations DESC, m.id ASC'
            )
        ).fetchall()
    leaderboard: list[dict[str, Any]] = []
    for row in rows:
        stats = {
            'total_distance_km': _safe_float(row['total_distance_km']),
            'activity_participations': _safe_int(row['activity_participations']),
            'monthly_checkin_days': _safe_int(row['monthly_checkin_days']),
            'streak_days': 0,
            'best_pace_seconds_per_km': 0,
            'member_age_days': max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(row['created_at']).replace('Z', '+00:00'))).days),
        }
        earned, _ = _evaluate_rules(stats)
        leaderboard.append(
            {
                'member_id': _safe_int(row['member_id']),
                'member_name': str(row['member_name'] or ''),
                'achievement_count': len(earned),
                'earned_achievements': [item['key'] for item in earned],
                'total_distance_km': stats['total_distance_km'],
            }
        )
    return leaderboard


@router.get('/{member_id}', response_model=ApiResponse)
def read_member_achievements(member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """读取成员已获得和未获得的成就列表。"""
    admin_or_leader(current_user)
    stats = _load_member_statistics(member_id)
    earned, locked = _evaluate_rules(stats)
    return ApiResponse(data={'member_id': member_id, 'member_name': stats['member_name'], 'earned': earned, 'locked': locked}, message='成员成就获取成功')


@router.get('/leaderboard', response_model=ApiResponse)
def read_achievement_leaderboard(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """按成就数量返回排行。"""
    admin_or_leader(current_user)
    return ApiResponse(data=_leaderboard_rows(), message='成就排行榜获取成功')
