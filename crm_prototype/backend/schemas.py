from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class SegmentBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    criteria: Optional[str] = None


class SegmentCreate(SegmentBase):
    pass


class SegmentRead(SegmentBase):
    id: int

    class Config:
        from_attributes = True


class CustomerBase(BaseModel):
    email: EmailStr
    full_name: str
    phone_number: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    preferences: Optional[str] = None
    is_vip: bool = False


class CustomerCreate(CustomerBase):
    segment_ids: Optional[List[int]] = None


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    preferences: Optional[str] = None
    is_vip: Optional[bool] = None
    segment_ids: Optional[List[int]] = None


class CustomerRead(CustomerBase):
    id: int
    created_at: datetime
    segments: List[SegmentRead] = []

    class Config:
        from_attributes = True


class CampaignBase(BaseModel):
    name: str
    channel: str
    status: str = "draft"
    scheduled_at: Optional[datetime] = None
    budget: Optional[int] = None
    notes: Optional[str] = None
    segment_id: Optional[int] = None


class CampaignCreate(CampaignBase):
    pass


class CampaignRead(CampaignBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageTemplateBase(BaseModel):
    title: str
    channel: str
    content: str
    language: str = "es"
    is_approved: bool = False


class MessageTemplateCreate(MessageTemplateBase):
    pass


class MessageTemplateRead(MessageTemplateBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class InteractionLogBase(BaseModel):
    customer_id: int
    channel: str
    direction: str = "outbound"
    message: str
    occurred_at: Optional[datetime] = None


class InteractionLogCreate(InteractionLogBase):
    pass


class InteractionLogRead(InteractionLogBase):
    id: int
    occurred_at: datetime

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    total_customers: int
    vip_customers: int
    active_campaigns: int
    queued_messages: int
