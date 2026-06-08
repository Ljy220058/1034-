from __future__ import annotations

from dataclasses import dataclass
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
    metric: str
    threshold: int

    def as_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'metric': self.metric,
            'threshold': self.threshold,
        }


ACHIEVEMENT_RULES: tuple[AchievementRule, ...] = (
    AchievementRule('entry_runner', '入门跑者', '累计里程达到 10 公里。', 'total_distance_km', 10),
    AchievementRule('streak_star', '坚持之星', '连续打卡达到 7 天。', 'continuous_checkin_days', 7),
    AchievementRule('monthly_soldier', '月度标兵', '本月出勤达到 15 天。', 'monthly_attendance_days', 15),
    AchievementRule('distance_master', '里程达人', '累计里程达到 100 公里。', 'total_distance_km', 100),
    AchievementRule('activity_pioneer', '活动先锋', '参与活动达到 10 次。', 'activity_participation_count', 10),
)


def _build_sample_achievements() -> list[dict[str, Any]]:
    """构建成就样例列表。"""
    return [rule.as_dict() for rule in ACHIEVEMENT_RULES]


@router.get('/sample', response_model=ApiResponse)
def get_achievement_sample() -> ApiResponse:
    """返回成就规则样例。"""
    return ApiResponse(
        data={
            'rules': _build_sample_achievements(),
            'summary': {
                'count': len(ACHIEVEMENT_RULES),
                'note': '成就规则为纯函数定义，不依赖数据库。',
            },
        },
        message='成就规则样例获取成功',
    )
