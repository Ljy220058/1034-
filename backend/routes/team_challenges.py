from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/team-challenges', tags=['team-challenges'])
DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'team_challenges.json'


@dataclass(frozen=True)
class TeamChallengeRecord:
    """团队跑量挑战记录。

    Attributes:
        id: 挑战 ID。
        title: 挑战标题。
        target_distance_km: 目标总跑量。
        start_date: 开始日期。
        end_date: 结束日期。
        team_count: 分队数量。
        members: 报名成员列表。
        assignments: 分队结果。
        created_at: 创建时间。
    """

    id: int
    title: str
    target_distance_km: float
    start_date: str
    end_date: str
    team_count: int
    members: list[dict[str, Any]]
    assignments: list[dict[str, Any]]
    created_at: str


class TeamChallengeCreate(BaseModel):
    """团队跑量挑战创建请求。"""

    title: str = Field(min_length=1, max_length=120)
    target_distance_km: float = Field(gt=0)
    start_date: date
    end_date: date
    team_count: int = Field(ge=2, le=20)

    @field_validator('title')
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """清理标题空白。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('标题不能为空')
        return cleaned

    @field_validator('end_date')
    @classmethod
    def validate_date_order(cls, value: date, info: Any) -> date:
        """验证结束日期晚于开始日期。"""
        start_date = info.data.get('start_date')
        if isinstance(start_date, date) and value < start_date:
            raise ValueError('结束日期不能早于开始日期')
        return value


class TeamChallengeRandomize(BaseModel):
    """随机分队请求。"""

    member_ids: list[int] = Field(min_length=1)
    team_count: int = Field(ge=2, le=20)

    @field_validator('member_ids')
    @classmethod
    def validate_member_ids(cls, value: list[int]) -> list[int]:
        """验证成员 ID 列表。"""
        unique_ids = list(dict.fromkeys(value))
        if len(unique_ids) != len(value):
            raise ValueError('成员 ID 不能重复')
        if any(member_id <= 0 for member_id in value):
            raise ValueError('成员 ID 必须大于 0')
        return value


class TeamChallengeRankingQuery(BaseModel):
    """团队跑量排行查询请求。"""

    challenge_id: int = Field(gt=0)



def _load_records() -> list[TeamChallengeRecord]:
    """读取挑战数据。"""
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open('r', encoding='utf-8') as file_handle:
        raw_items = json.load(file_handle)
    return [TeamChallengeRecord(**item) for item in raw_items]



def _save_records(records: list[TeamChallengeRecord]) -> None:
    """保存挑战数据。"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(record) for record in records]
    with DATA_FILE.open('w', encoding='utf-8') as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)



def _extract_member_distance(member: dict[str, Any]) -> float:
    """获取成员跑量。"""
    raw_value = member.get('distance_km', 0)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0



def _build_assignments(member_ids: list[int], team_count: int) -> list[dict[str, Any]]:
    """随机生成分队结果。"""
    shuffled_ids = list(member_ids)
    random.shuffle(shuffled_ids)
    teams: list[list[int]] = [[] for _ in range(team_count)]
    for index, member_id in enumerate(shuffled_ids):
        teams[index % team_count].append(member_id)
    return [
        {'team_id': index + 1, 'member_ids': team, 'member_count': len(team)}
        for index, team in enumerate(teams)
    ]



def _current_ranking(record: TeamChallengeRecord) -> list[dict[str, Any]]:
    """计算实时排行。"""
    team_rows: list[dict[str, Any]] = []
    for assignment in record.assignments:
        member_ids = assignment['member_ids']
        members = [member for member in record.members if member['id'] in member_ids]
        total_distance = round(sum(_extract_member_distance(member) for member in members), 2)
        completed_ratio = 0.0
        if record.target_distance_km > 0:
            completed_ratio = round(min(total_distance / record.target_distance_km * 100, 100.0), 2)
        team_rows.append(
            {
                'team_id': assignment['team_id'],
                'total_distance_km': total_distance,
                'completed_percent': completed_ratio,
                'member_contributions': sorted(
                    [
                        {
                            'member_id': member['id'],
                            'member_name': member.get('name', f'成员{member["id"]}'),
                            'distance_km': _extract_member_distance(member),
                        }
                        for member in members
                    ],
                    key=lambda item: (-item['distance_km'], item['member_id']),
                ),
            }
        )
    return sorted(team_rows, key=lambda item: (-item['total_distance_km'], item['team_id']))


@router.post('/create', response_model=ApiResponse)
def create_team_challenge(payload: TeamChallengeCreate) -> ApiResponse:
    """创建团队跑量挑战。"""
    records = _load_records()
    next_id = max((record.id for record in records), default=0) + 1
    record = TeamChallengeRecord(
        id=next_id,
        title=payload.title,
        target_distance_km=payload.target_distance_km,
        start_date=payload.start_date.isoformat(),
        end_date=payload.end_date.isoformat(),
        team_count=payload.team_count,
        members=[],
        assignments=[],
        created_at=datetime.now().isoformat(timespec='seconds'),
    )
    records.append(record)
    _save_records(records)
    return ApiResponse(data=asdict(record), message='挑战创建成功')


@router.post('/randomize', response_model=ApiResponse)
def randomize_team_challenge(payload: TeamChallengeRandomize) -> ApiResponse:
    """将报名成员随机分入多个队伍。"""
    records = _load_records()
    if not records:
        raise HTTPException(status_code=404, detail='挑战不存在')
    latest_record = records[-1]
    assignments = _build_assignments(payload.member_ids, payload.team_count)
    updated_record = TeamChallengeRecord(
        id=latest_record.id,
        title=latest_record.title,
        target_distance_km=latest_record.target_distance_km,
        start_date=latest_record.start_date,
        end_date=latest_record.end_date,
        team_count=payload.team_count,
        members=[{'id': member_id, 'name': f'成员{member_id}', 'distance_km': 0} for member_id in payload.member_ids],
        assignments=assignments,
        created_at=latest_record.created_at,
    )
    records[-1] = updated_record
    _save_records(records)
    return ApiResponse(data={'challenge_id': updated_record.id, 'assignments': assignments}, message='随机分队完成')


@router.get('/ranking/{challenge_id}', response_model=ApiResponse)
def read_team_challenge_ranking(challenge_id: int) -> ApiResponse:
    """获取团队跑量实时排行。"""
    records = _load_records()
    record = next((item for item in records if item.id == challenge_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail='挑战不存在')
    return ApiResponse(
        data={
            'challenge_id': record.id,
            'title': record.title,
            'target_distance_km': record.target_distance_km,
            'ranking': _current_ranking(record),
        },
        message='排行获取成功',
    )
