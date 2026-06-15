from pydantic import BaseModel, Field
from typing import Optional


class PalmistryResponse(BaseModel):
    report: str = Field(..., description="手相分析报告（Markdown 格式）")
    metadata: Optional[dict] = Field(default=None, description="调用元数据")
