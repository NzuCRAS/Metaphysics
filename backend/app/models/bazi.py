from pydantic import BaseModel, Field
from typing import Optional


class BaziRequest(BaseModel):
    birth_date: str = Field(..., description="公历出生日期，格式 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$")
    birth_time: str = Field(..., description="出生时间，格式 HH:MM", pattern=r"^\d{2}:\d{2}$")
    gender: str = Field(..., description="性别", pattern=r"^(male|female|男|女)$")
    birthplace: str = Field(..., description="出生地，如：中国浙江省杭州市")


class BaziResponse(BaseModel):
    report: str = Field(..., description="八字命理分析报告（Markdown 格式）")
    metadata: Optional[dict] = Field(default=None, description="调用元数据")
