from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

MemberRole = Literal['leader', 'admin', 'member']
RegistrationStatus = Literal['registered', 'cancelled']
AnnouncementStatus = Literal['draft', 'published']


class ApiResponse(BaseModel):
    data: Any
    message: str = '成功'


class MemberBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    role: MemberRole = 'member'
    running_years: int = Field(default=0, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)


class MemberCreate(MemberBase):
    pass


class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    role: Optional[MemberRole] = None
    running_years: Optional[int] = Field(default=None, ge=0)
    pace: Optional[str] = Field(default=None, max_length=30)
    usual_distance_km: Optional[float] = Field(default=None, ge=0)
    training_goal: Optional[str] = Field(default=None, max_length=200)


class UserRegister(MemberBase):
    phone: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    phone: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class MemberOut(MemberBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ActivityBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    max_participants: Optional[int] = Field(default=None, gt=0)

    model_config = {'extra': 'allow'}


class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    max_participants: Optional[int] = Field(default=None, gt=0)
    model_config = {'extra': 'allow'}


class ActivityUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    start_time: Optional[datetime] = None
    location: Optional[str] = Field(default=None, min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    max_participants: Optional[int] = Field(default=None, gt=0)


class ActivityOut(ActivityBase):
    id: int
    created_at: datetime
    updated_at: datetime


class RegistrationCreate(BaseModel):
    member_id: int = Field(gt=0)


class RegistrationOut(BaseModel):
    id: int
    activity_id: int
    member_id: int
    status: RegistrationStatus
    created_at: datetime


class AttendanceCreate(BaseModel):
    member_id: int = Field(gt=0)
    activity_id: int = Field(default=0)
    checked_in_at: Optional[datetime] = None
    gps_checked: bool = False


class WorkerIntakeCreate(BaseModel):
    worker_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    status: Literal['active', 'paused', 'disabled'] = 'active'
    capabilities: list[str] = Field(default_factory=list)


def _contains_chinese(value: str) -> bool:
    """判断文本是否包含中文字符。

    Args:
        value: 待检查文本。

    Returns:
        包含中文字符时返回 True。
    """
    return any('\u4e00' <= char <= '\u9fff' for char in value)


class TaskItemCreate(BaseModel):
    """工作区任务卡片创建请求。

    Attributes:
        task_key: 工作区内唯一任务键。
        title: 中文任务标题。
        description: 中文任务描述。
        status: 任务状态。
        assignee: 负责人。
        priority: 任务优先级。
    """

    task_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    status: Literal['todo', 'ready', 'running', 'done'] = 'todo'
    assignee: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=0, ge=0, lt=1000)

    @field_validator('task_key', 'title', 'description', mode='after')
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """清理必填文本字段前后空白。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('字段不能为空')
        return cleaned

    @field_validator('title', mode='after')
    @classmethod
    def validate_chinese_title(cls, value: str) -> str:
        """校验标题包含中文。"""
        if not _contains_chinese(value):
            raise ValueError('标题必须包含中文')
        return value

    @field_validator('description', mode='after')
    @classmethod
    def validate_chinese_description(cls, value: str) -> str:
        """校验描述包含中文。"""
        if not _contains_chinese(value):
            raise ValueError('描述必须包含中文')
        return value

    @field_validator('assignee', mode='after')
    @classmethod
    def normalize_assignee(cls, value: str) -> str:
        """清理负责人字段。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('负责人不能为空')
        return cleaned


class WorkerIntakeOut(BaseModel):
    id: int
    worker_key: str
    name: str
    status: Literal['active', 'paused', 'disabled']
    capabilities: list[str]
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class WorkspaceTaskOut(BaseModel):
    id: int
    worker_key: str
    name: str
    status: Literal['active', 'paused', 'disabled']
    capabilities: list[str]
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class AttendanceOut(BaseModel):
    id: int
    activity_id: int
    member_id: int
    status: Literal['signed_in', 'absent']
    signed_in_at: datetime
    gps_checked: bool


class AnnouncementBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: AnnouncementStatus = 'published'
    is_pinned: bool = False
    model_config = {'extra': 'allow'}


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    status: AnnouncementStatus = 'published'
    is_pinned: bool = False
    model_config = {'extra': 'allow'}


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    body: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AnnouncementStatus] = None
    is_pinned: Optional[bool] = None


class AnnouncementOut(AnnouncementBase):
    id: int
    created_at: datetime


class RegisterRequest(MemberCreate):
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)

