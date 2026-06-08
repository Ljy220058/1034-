from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/achievements', tags=['achievements'])


@dataclass(frozen=True)
class AchievementRule:
    """成就规则定义。"""

    key: str
    name: str
    description: str
    metric_key: str
    threshold: int

    def as_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'metric_key': self.metric_key,
            'threshold': self.threshold,
        }


ACHIEVEMENT_RULES: list[AchievementRule] = [
    AchievementRule(
        key='beginner_runner',
        name='入门跑者',
        description='累计里程达到 10 公里。',
        metric_key='total_distance_km',
        threshold=10,
    ),
    AchievementRule(
        key='streak_star',
        name='坚持之星',
        description='连续打卡天数达到 7 天。',
        metric_key='consecutive_checkin_days',
        threshold=7,
    ),
    AchievementRule(
        key='monthly_model',
        name='月度标兵',
        description='本月出勤达到 15 天。',
        metric_key='monthly_attendance_days',
        threshold=15,
    ),
    AchievementRule(
        key='distance_hero',
        name='里程达人',
        description='累计里程达到 100 公里。',
        metric_key='total_distance_km',
        threshold=100,
    ),
    AchievementRule(
        key='activity_pioneer',
        name='活动先锋',
        description='参与活动数达到 10 场。',
        metric_key='activity_count',
        threshold=10,
    ),
]


def evaluate_achievements(metrics: dict[str, int]) -> list[dict[str, Any]]:
    """根据成员数据评估成就。

    Args:
        metrics: 成员统计数据。

    Returns:
        命中的成就列表。
    """
    earned: list[dict[str, Any]] = []
    for rule in ACHIEVEMENT_RULES:
        value = metrics.get(rule.metric_key, 0)
        if value >= rule.threshold:
            earned.append(
                {
                    'key': rule.key,
                    'name': rule.name,
                    'description': rule.description,
                    'threshold': rule.threshold,
                    'value': value,
                }
            )
    return earned


def build_sample_payload() -> dict[str, Any]:
    """构建样例返回数据。"""
    metrics = {
        'total_distance_km': 128,
        'consecutive_checkin_days': 9,
        'monthly_attendance_days': 18,
        'activity_count': 12,
    }
    return {
        'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'rules': [rule.as_dict() for rule in ACHIEVEMENT_RULES],
        'metrics_example': metrics,
        'earned_example': evaluate_achievements(metrics),
        'note': '成就规则仅基于传入数据计算，不依赖数据库或 fixture。',
    }


@router.get('/sample')
def sample_achievements() -> ApiResponse:
    """返回成就规则样例。

    Returns:
        包含所有成就定义与规则说明的 ApiResponse。
    """
    return ApiResponse(data=build_sample_payload(), message='成就规则样例获取成功')
