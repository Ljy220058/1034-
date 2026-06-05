from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

MemberRole = Literal['leader', 'admin', 'member']
RegistrationStatus = Literal['registered', 'cancelled']
AnnouncementStatus = Literal['draft', 'published']


class ApiResponse(BaseModel):
    data: Any


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

    model_config = {'extra': 'allow'}


class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_time: datetime
    location: str = Field(min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    model_config = {'extra': 'allow'}


class ActivityUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    start_time: Optional[datetime] = None
    location: Optional[str] = Field(default=None, min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, max_length=200)
    distance_km: Optional[float] = Field(default=None, ge=0)
    pace_group: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)


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
    activity_id: int = Field(gt=0)
    checked_in_at: Optional[datetime] = None
    gps_checked: bool = False


class WorkerIntakeCreate(BaseModel):
    worker_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    status: Literal['active', 'paused', 'disabled'] = 'active'
    capabilities: list[str] = Field(default_factory=list)


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

