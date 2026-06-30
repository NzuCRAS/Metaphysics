from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Index
from sqlalchemy.sql import func

from app.db import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(20), nullable=False, index=True)
    region = Column(String(10), nullable=False, index=True, default="global")
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500))
    path = Column(String(500))
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    cost_cny = Column(Numeric(12, 6), nullable=True)

    __table_args__ = (
        Index("ix_analytics_events_type_ts", "event_type", "timestamp"),
        Index("ix_analytics_events_region_ts", "region", "timestamp"),
    )


class PageViewPayload(BaseModel):
    region: Optional[str] = Field(default="global", max_length=10)


class TrafficSummary(BaseModel):
    date: date
    total_pageviews: int
    total_bazi_requests: int
    total_bazi_reports: int
    total_palmistry_requests: int
    total_palmistry_reports: int
    total_cost_cny: Decimal = Field(..., decimal_places=6)
    unique_ips: int
    by_region: dict
    cost_by_region: dict
    hourly: list
    half_hourly: list


class EventRow(BaseModel):
    id: int
    event_type: str
    region: str
    ip_address: str
    user_agent: Optional[str]
    path: Optional[str]
    timestamp: datetime
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    cost_cny: Optional[Decimal]

    class Config:
        from_attributes = True
