from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from fastapi import APIRouter

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/achievements', tags=['achievements'])

_MIN_MILEAGE_KM: Final[int] = 10
_MIN_STREAK_DAYS: Final[int] = 7
_MIN_MONTH_ATTENDANCE_DAYS: Final[int] = 15
_MIN_TOTAL_MILEAGE_KM: Final[int] = 100
_MIN_ACTIVITY_COUNT: Final[int] = 10


@dataclass(frozen=True)
class AchievementRule:
    """成就规则定义。

    Attributes:
        name: 成就名称。
        description: 规则说明。
        metric_key: 统计指标键。
        threshold: 达成阈值。
        unit: 指标单位。
    """

    name: str
    description: str
    metric_key: str
    threshold: int
    unit: str

    def as_dict(self) -> dict[str, Any]:
        """转为接口返回字典。"""
        return {
            'name': self.name,
            'description': self.description,
            'rule': {
                'metric_key': self.metric_key,
                'threshold': self.threshold,
                'unit': self.unit,
            },
        }


def _build_achievement_rules() -> list[AchievementRule]:
    """构建成就规则清单。

    Returns:
        成就规则列表。
    """
    return [
        AchievementRule(
            name='入门跑者',
            description='累计里程达到 10 公里即可获得。',
            metric_key='beginner_runner',
            threshold=_MIN_MILEAGE_KM,
            unit='公里',
        ),
        AchievementRule(
            name='坚持之星',
            description='连续打卡天数达到 7 天即可获得。',
            metric_key='streak_keeper',
            threshold=_MIN_STREAK_DAYS,
            unit='天',
        ),
        AchievementRule(
            name='月度标兵',
            description='本月出勤天数达到 15 天即可获得。',
            metric_key='monthly_attendance',
            threshold=_MIN_MONTH_ATTENDANCE_DAYS,
            unit='天',
        ),
        AchievementRule(
            name='里程达人',
            description='累计里程达到 100 公里即可获得。',
            metric_key='mileage_master',
            threshold=_MIN_TOTAL_MILEAGE_KM,
            unit='公里',
        ),
        AchievementRule(
            name='活动先锋',
            description='参与活动数达到 10 场即可获得。',
            metric_key='activity_pioneer',
            threshold=_MIN_ACTIVITY_COUNT,
            unit='场',
        ),
    ]


@router.get('/sample')
def sample_achievements() -> dict[str, Any]:
    """返回成就定义和规则说明。

    Returns:
        ApiResponse 结构的成就样例数据。
    """
    rules = _build_achievement_rules()
    payload = {
        'earned_example': [rule.as_dict() for rule in rules],
        'summary': {
            'count': len(rules),
            'data_source': '纯函数规则模块',
            'notes': [
                '不依赖数据库',
                '不依赖 fixture',
                '规则仅用于展示与前端说明',
            ],
        },
    }
    return ApiResponse(data=payload, message='成就规则样例获取成功').model_dump()
