from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/training', tags=['training'])
ExperienceLevel = Literal['beginner', 'intermediate', 'advanced']


class PaceZone(BaseModel):
    """单个训练类型的配速区间。

    Attributes:
        name: 中文训练类型名称。
        pace_range: 配速区间文本，格式为 mm:ss/km-mm:ss/km。
        min_seconds_per_km: 区间下限，单位秒/公里。
        max_seconds_per_km: 区间上限，单位秒/公里。
        description: 训练用途说明。
    """

    name: str
    pace_range: str
    min_seconds_per_km: int
    max_seconds_per_km: int
    description: str


class TrainingPaceInput(BaseModel):
    """训练配速区间计算输入。

    计算假设：以目标完赛平均配速作为基准；不同训练经验等级对应不同训练强度系数；
    当周跑量低于 15 公里时整体放慢 5%，高于 70 公里时略收紧 2%。该算法用于跑团训练建议，
    不替代专业教练或医疗意见。
    """

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
        'long_run': (1.225, 1.37),
    },
    'advanced': {
        'easy_run': (1.125, 1.22),
        'tempo_run': (0.935, 0.985),
        'interval_run': (0.885, 0.925),
        'long_run': (1.165, 1.305),
    },
}


def _minutes_to_pace_text(minutes_per_km: float) -> str:
    """将分钟/公里转换为 mm:ss/km 文本。"""
    total_seconds = int(round(minutes_per_km * 60))
    minutes, seconds = divmod(total_seconds, 60)
    return f'{minutes}:{seconds:02d}/km'


def _apply_weekly_mileage_adjustment(base_minutes_per_km: float, weekly_mileage_km: float) -> float:
    """根据周跑量微调基准配速。"""
    if weekly_mileage_km < 15:
        return base_minutes_per_km * 1.05
    if weekly_mileage_km > 70:
        return base_minutes_per_km * 0.98
    return base_minutes_per_km


def _build_pace_zone(name: str, factor_range: tuple[float, float], base_minutes_per_km: float, weekly_mileage_km: float, description: str) -> PaceZone:
    """构造单个训练配速区间。"""
    min_minutes = _apply_weekly_mileage_adjustment(base_minutes_per_km * factor_range[0], weekly_mileage_km)
    max_minutes = _apply_weekly_mileage_adjustment(base_minutes_per_km * factor_range[1], weekly_mileage_km)
    lower = min(min_minutes, max_minutes)
    upper = max(min_minutes, max_minutes)
    return PaceZone(
        name=name,
        pace_range=f'{_minutes_to_pace_text(lower)}-{_minutes_to_pace_text(upper)}',
        min_seconds_per_km=int(round(lower * 60)),
        max_seconds_per_km=int(round(upper * 60)),
        description=description,
    )


def _validation_detail_message(exc: Exception) -> str:
    """将校验异常转换为中文错误信息。"""
    message = str(exc)
    if 'Value error,' in message:
        return message.split('Value error,', 1)[1].strip()
    return message or '训练配速参数无效'


@router.post('/pace-zones', response_model=ApiResponse)
def calculate_training_pace(payload: TrainingPaceInput) -> ApiResponse:
    """根据比赛目标计算训练配速区间。

    假设：
    - 目标配速 = 目标完赛时间 / 目标距离。
    - 经验等级通过固定系数调整不同训练类型的推荐配速。
    - 周跑量过低时整体放慢、过高时略收紧。

    Args:
        payload: 训练配速计算输入。

    Returns:
        包含 easy/tempo/interval/long 四类配速区间的响应。

    Raises:
        HTTPException: 当输入非法时返回 422。
    """
    try:
        target_pace_minutes = payload.target_time_minutes / payload.target_distance_km
        factors = EXPERIENCE_FACTORS[payload.experience_level]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=_validation_detail_message(exc)) from exc

    zone_list = [
        ('easy_run', '轻松跑', factors['easy_run'], '用于恢复和基础有氧积累'),
        ('tempo_run', '节奏跑', factors['tempo_run'], '用于提升阈值与持续输出能力'),
        ('interval_run', '间歇跑', factors['interval_run'], '用于提升速度与乳酸耐受'),
        ('long_run', '长距离跑', factors['long_run'], '用于增强耐力与比赛后程稳定性'),
    ]
    zones = {
        key: _build_pace_zone(name, factor_range, target_pace_minutes, payload.weekly_mileage_km, description)
        for key, name, factor_range, description in zone_list
    }

    return ApiResponse(
        data={
            'target_pace': _minutes_to_pace_text(target_pace_minutes),
            'target': {
                'distance_km': payload.target_distance_km,
                'time_minutes': payload.target_time_minutes,
                'weekly_mileage_km': payload.weekly_mileage_km,
                'experience_level': payload.experience_level,
            },
            'zones': zones,
        },
        message='配速区间计算完成',
    )


@router.get('/pace-zones/sample', response_model=ApiResponse)
def calculate_training_pace_sample() -> ApiResponse:
    """返回训练配速接口示例。"""
    return calculate_training_pace(
        TrainingPaceInput(
            target_distance_km=10,
            target_time_minutes=50,
            weekly_mileage_km=35,
            experience_level='intermediate',
        )
    )
