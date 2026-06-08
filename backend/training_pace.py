from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/training', tags=['training'])

ExperienceLevel = Literal['beginner', 'intermediate', 'advanced']


class PaceZone(BaseModel):
    """单个训练类型的配速区间。"""

    name: str
    pace_range: str
    min_seconds_per_km: int
    max_seconds_per_km: int
    description: str


class TrainingPaceInput(BaseModel):
    """训练配速区间计算输入。"""

    target_distance_km: float = Field(description='目标比赛距离，单位公里')
    target_time_minutes: float = Field(description='目标完赛时间，单位分钟')
    weekly_mileage_km: float = Field(description='当前周跑量，单位公里')
    experience_level: ExperienceLevel = Field(description='训练经验等级：beginner/intermediate/advanced')

    @field_validator('target_distance_km', 'target_time_minutes', 'weekly_mileage_km')
    @classmethod
    def validate_positive_number(cls, value: float) -> float:
        """校验距离、时间和周跑量都必须为正数。"""
        if value <= 0:
            raise ValueError('输入值必须大于 0')
        return value


EXPERIENCE_FACTORS: dict[ExperienceLevel, dict[str, tuple[float, float]]] = {
    'beginner': {
        'easy_run': (1.225, 1.33),
        'tempo_run': (1.035, 1.085),
        'interval_run': (0.87, 0.93),
        'long_run': (1.285, 1.44),
    },
    'intermediate': {
        'easy_run': (1.175, 1.28),
        'tempo_run': (0.985, 1.035),
        'interval_run': (0.88, 0.93),
        'long_run': (1.22, 1.35),
    },
    'advanced': {
        'easy_run': (1.14, 1.22),
        'tempo_run': (0.95, 1.00),
        'interval_run': (0.82, 0.88),
        'long_run': (1.18, 1.30),
    },
}

ZONE_LABELS: dict[str, tuple[str, str]] = {
    'easy_run': ('轻松跑', '有氧基础训练，可完整对话，优先控制强度。'),
    'tempo_run': ('节奏跑', '接近乳酸阈值的持续跑，体感偏吃力但可维持。'),
    'interval_run': ('间歇跑', '短时间高强度训练，需搭配充分热身和恢复慢跑。'),
    'long_run': ('长距离跑', '耐力训练配速，比轻松跑更保守，避免过度疲劳。'),
}


def _pace_text(seconds_per_km: int) -> str:
    """把每公里秒数格式化为中文跑步常用配速文本。"""
    minutes, seconds = divmod(max(1, seconds_per_km), 60)
    return f'{minutes}:{seconds:02d}/km'


def _mileage_adjustment(weekly_mileage_km: float) -> float:
    """根据当前周跑量返回保守调节系数。"""
    if weekly_mileage_km < 15:
        return 0.05
    if weekly_mileage_km < 30:
        return 0.0
    if weekly_mileage_km > 70:
        return -0.02
    return 0.0


def _zone_seconds(target_pace_seconds: int, factors: tuple[float, float], adjustment: float) -> tuple[int, int]:
    """按目标配速和区间系数计算配速上下限。"""
    fast_factor, slow_factor = factors
    fast_seconds = int(round(target_pace_seconds * max(0.5, fast_factor + adjustment)))
    slow_seconds = int(round(target_pace_seconds * max(0.5, slow_factor + adjustment)))
    return min(fast_seconds, slow_seconds), max(fast_seconds, slow_seconds)


def calculate_training_pace_zones(payload: TrainingPaceInput) -> dict[str, Any]:
    """计算建议训练配速区间。

    计算假设：以目标完赛平均配速作为基准；不同训练经验等级对应不同训练强度系数；当周跑量低于 15 公里时整体放慢
    5%，高于 70 公里时略收紧 2%。该算法用于跑团训练建议，不替代专业教练或医疗意见。
    """
    target_pace_seconds = int(round(payload.target_time_minutes * 60 / payload.target_distance_km))
    adjustment = _mileage_adjustment(payload.weekly_mileage_km)
    zones: dict[str, dict[str, Any]] = {}

    for key, factors in EXPERIENCE_FACTORS[payload.experience_level].items():
        fast_seconds, slow_seconds = _zone_seconds(target_pace_seconds, factors, adjustment)
        name, description = ZONE_LABELS[key]
        zones[key] = PaceZone(
            name=name,
            pace_range=f'{_pace_text(fast_seconds)}-{_pace_text(slow_seconds)}',
            min_seconds_per_km=fast_seconds,
            max_seconds_per_km=slow_seconds,
            description=description,
        ).model_dump()

    return {
        'target_pace': _pace_text(target_pace_seconds),
        'target_pace_seconds_per_km': target_pace_seconds,
        'experience_level': payload.experience_level,
        'weekly_mileage_km': payload.weekly_mileage_km,
        'zones': zones,
        'assumptions': [
            '以目标完赛平均配速作为所有训练配速区间的基准。',
            '训练经验越高，节奏跑和间歇跑区间相对更接近或快于目标配速。',
            '周跑量低于 15 公里时整体放慢 5%，优先降低受伤风险。',
        ],
    }


@router.post('/pace-zones', response_model=ApiResponse)
def calculate_training_pace_zones_endpoint(payload: TrainingPaceInput) -> ApiResponse:
    """计算跑团训练建议配速区间。"""
    data = calculate_training_pace_zones(payload)
    return ApiResponse(data=data, message='配速区间计算完成')
