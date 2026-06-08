from __future__ import annotations

"""成就规则纯函数模块。"""

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/achievements', tags=['achievements'])

AchievementRuleFn = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class AchievementRule:
    """成就规则定义。"""

    key: str
    name: str
    threshold: int
    description: str
    source: str
    rule: AchievementRuleFn

    def as_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """转换为规则说明字典。"""
        return {
            'key': self.key,
            'name': self.name,
            'threshold': self.threshold,
            'description': self.description,
            'source': self.source,
            'achieved': self.rule(data),
        }


def _to_non_negative_int(value: Any) -> int:
    """把输入安全转换为非负整数。"""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    return 0


def _current_month_days(current_month_attendance_days: Any) -> int:
    """提取本月出勤天数。"""
    return _to_non_negative_int(current_month_attendance_days)


def _build_rules() -> list[AchievementRule]:
    """构建成就规则列表。"""
    return [
        AchievementRule(
            key='rookie-runner',
            name='入门跑者',
            threshold=10,
            description='累计里程达到 10 公里即可解锁。',
            source='累计里程',
            rule=lambda data: _to_non_negative_int(data.get('total_distance_km')) >= 10,
        ),
        AchievementRule(
            key='streak-star',
            name='坚持之星',
            threshold=7,
            description='连续打卡天数达到 7 天即可解锁。',
            source='连续打卡天数',
            rule=lambda data: _to_non_negative_int(data.get('consecutive_checkin_days')) >= 7,
        ),
        AchievementRule(
            key='monthly-soldier',
            name='月度标兵',
            threshold=15,
            description='本月出勤达到 15 天即可解锁。',
            source='本月出勤天数',
            rule=lambda data: _current_month_days(data.get('current_month_attendance_days')) >= 15,
        ),
        AchievementRule(
            key='distance-master',
            name='里程达人',
            threshold=100,
            description='累计里程达到 100 公里即可解锁。',
            source='累计里程',
            rule=lambda data: _to_non_negative_int(data.get('total_distance_km')) >= 100,
        ),
        AchievementRule(
            key='activity-pioneer',
            name='活动先锋',
            threshold=10,
            description='参与活动数量达到 10 次即可解锁。',
            source='参与活动数',
            rule=lambda data: _to_non_negative_int(data.get('activity_count')) >= 10,
        ),
    ]


ACHIEVEMENT_RULES = _build_rules()


def evaluate_achievements(data: dict[str, Any]) -> list[dict[str, Any]]:
    """计算成就解锁结果。

    Args:
        data: 成就输入数据，支持 total_distance_km、consecutive_checkin_days、current_month_attendance_days、activity_count。

    Returns:
        成就规则及其解锁状态列表。
    """
    return [rule.as_dict(data) for rule in ACHIEVEMENT_RULES]


@router.get('/sample', response_model=ApiResponse)
def get_sample_achievements() -> ApiResponse:
    """返回成就样例定义和规则说明。"""
    return ApiResponse(
        data={
            'input_schema': {
                'total_distance_km': '累计里程，整数或可转为整数的数值',
                'consecutive_checkin_days': '连续打卡天数，整数或可转为整数的数值',
                'current_month_attendance_days': '本月出勤天数，整数或可转为整数的数值',
                'activity_count': '参与活动数量，整数或可转为整数的数值',
            },
            'rules': [
                {
                    'key': rule.key,
                    'name': rule.name,
                    'threshold': rule.threshold,
                    'description': rule.description,
                    'source': rule.source,
                }
                for rule in ACHIEVEMENT_RULES
            ],
            'examples': {
                'unlock_all': evaluate_achievements(
                    {
                        'total_distance_km': 120,
                        'consecutive_checkin_days': 9,
                        'current_month_attendance_days': 18,
                        'activity_count': 12,
                    }
                ),
                'unlock_none': evaluate_achievements(
                    {
                        'total_distance_km': 0,
                        'consecutive_checkin_days': 0,
                        'current_month_attendance_days': 0,
                        'activity_count': 0,
                    }
                ),
            },
        },
        message='已返回成就样例定义',
    )
