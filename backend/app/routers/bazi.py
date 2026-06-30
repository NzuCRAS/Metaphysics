from fastapi import APIRouter, HTTPException, Request, Header, Depends
from typing import Optional
import logging

from app.models.bazi import BaziRequest, BaziResponse
from app.config import settings
from app.db import get_db_optional
from app.services.providers.openai_compatible_provider import create_llm_client
from app.services.prompt_manager import prompt_manager
from app.services.text_cleaner import clean_report
from app.services.analytics import EVENT_BAZI_REQUEST, EVENT_BAZI_REPORT, record_event
from app.services.cost_tracker import CostTracker


router = APIRouter()
logger = logging.getLogger(__name__)

cost_tracker = CostTracker(
    input_price_per_m=settings.input_token_price_cny_per_m,
    output_price_per_m=settings.output_token_price_cny_per_m,
    max_daily_cny=settings.max_daily_cost_cny,
    max_output_tokens=settings.llm_max_tokens,
    safety_factor=settings.cost_safety_factor,
)


def _region(header: Optional[str]) -> str:
    if header in {"cn", "eu", "us"}:
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
        if db is not None:
            await record_event(db, EVENT_BAZI_REQUEST, request, region)

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

        if db is not None:
            await cost_tracker.check_budget(db, normalized)

        report = await client.complete(normalized)
        cleaned_report = clean_report(report)

        usage = client.last_usage or {}
        cost = cost_tracker.compute_cost(usage)
        if db is not None:
            await record_event(
                db,
                EVENT_BAZI_REPORT,
                request,
                region,
                tokens_input=usage.get("input_tokens"),
                tokens_output=usage.get("output_tokens"),
                cost_cny=cost,
            )

        return BaziResponse(
            report=cleaned_report,
            metadata={**client.metadata, "cost_cny": float(cost)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bazi analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again later.")
