from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import logging

from app.models.bazi import BaziRequest, BaziResponse
from app.config import settings
from app.db import get_db_optional
from app.services.providers.openai_compatible_provider import create_llm_client
from app.services.prompt_manager import prompt_manager
from app.services.text_cleaner import clean_report
from app.services.analytics import ALLOWED_REGIONS, EVENT_BAZI_REQUEST, EVENT_BAZI_REPORT
from app.services.llm_guard import complete_with_guard, stream_with_guard


router = APIRouter()
logger = logging.getLogger(__name__)


VALID_GENDERS = {"male", "female", "other", "男", "女"}


def _region(header: Optional[str]) -> str:
    if header in ALLOWED_REGIONS:
        return header
    return "global"


@router.post("/bazi", response_model=BaziResponse)
async def analyze_bazi(
    request: Request,
    bazi_request: BaziRequest,
    x_region: Optional[str] = Header(default=None),
    db: Optional = Depends(get_db_optional),
):
    region = _region(x_region)
    try:
        client = create_llm_client(settings)
        prompt = prompt_manager.get_bazi_prompt()

        messages = prompt.format_messages(
            birth_date=bazi_request.birth_date,
            birth_time=bazi_request.birth_time,
            gender=bazi_request.gender,
            birthplace=bazi_request.birthplace,
        )

        # 转换为 LLMClient 统一格式
        normalized = [{"role": "system", "content": messages[0].content}]
        for msg in messages[1:]:
            role = "human" if msg.type == "human" else "ai"
            normalized.append({"role": role, "content": msg.content})

        report, usage, metadata, cost = await complete_with_guard(
            request=request,
            db=db,
            region=region,
            client=client,
            messages=normalized,
            request_event_type=EVENT_BAZI_REQUEST,
            report_event_type=EVENT_BAZI_REPORT,
        )

        cleaned_report = clean_report(report)

        return BaziResponse(
            report=cleaned_report,
            metadata={**metadata, "cost_cny": float(cost)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bazi analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again later.")


@router.post("/bazi/stream")
async def analyze_bazi_stream(
    request: Request,
    bazi_request: BaziRequest,
    x_region: Optional[str] = Header(default=None),
    db: Optional = Depends(get_db_optional),
):
    region = _region(x_region)
    client = create_llm_client(settings)
    prompt = prompt_manager.get_bazi_prompt()

    messages = prompt.format_messages(
        birth_date=bazi_request.birth_date,
        birth_time=bazi_request.birth_time,
        gender=bazi_request.gender,
        birthplace=bazi_request.birthplace,
    )

    normalized = [{"role": "system", "content": messages[0].content}]
    for msg in messages[1:]:
        role = "human" if msg.type == "human" else "ai"
        normalized.append({"role": role, "content": msg.content})

    async def event_generator():
        async for sse_line in stream_with_guard(
            request=request,
            db=db,
            region=region,
            client=client,
            messages=normalized,
            request_event_type=EVENT_BAZI_REQUEST,
            report_event_type=EVENT_BAZI_REPORT,
        ):
            yield sse_line

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
