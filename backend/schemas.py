from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

MemberRole = Literal['leader', 'admin', 'member']
RegistrationStatus = Literal['registered', 'cancelled']
AttendanceStatus = Literal['signed_in', 'absent']


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


class ActivityCreate(ActivityBase):
    pass


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
    checked_in_at: Optional[datetime] = None
    gps_checked: bool = False


class AttendanceOut(BaseModel):
    id: int
    activity_id: int
    member_id: int
    status: AttendanceStatus
    signed_in_at: datetime
    gps_checked: bool


class AnnouncementBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    created_by: str = Field(default='system', max_length=80)


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementOut(AnnouncementBase):
    id: int
    created_at: datetime
