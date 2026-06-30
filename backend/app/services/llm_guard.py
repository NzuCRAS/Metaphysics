import logging
import time
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.analytics import record_event
from app.services.cost_tracker import CostTracker


logger = logging.getLogger(__name__)

cost_tracker = CostTracker(
    input_price_per_m=settings.input_token_price_cny_per_m,
    output_price_per_m=settings.output_token_price_cny_per_m,
    max_daily_cny=settings.max_daily_cost_cny,
    max_output_tokens=settings.llm_max_tokens,
    safety_factor=settings.cost_safety_factor,
)


async def complete_with_guard(
    request: Request,
    db: Optional[AsyncSession],
    region: str,
    client,
    messages: list[dict],
    request_event_type: str,
    report_event_type: str,
) -> tuple[str, dict, dict, Decimal]:
    """统一封装 LLM 调用：记录请求、检查预算、调用模型、记录报告与成本。

    返回 (cleaned_report, usage, metadata, cost_cny)。
    """
    if db is None:
        logger.error("LLM call attempted while analytics database is unavailable")
        raise HTTPException(
            status_code=503,
            detail="Cost tracking database is not available; LLM calls are disabled.",
        )

    await record_event(db, request_event_type, request, region)
    await cost_tracker.check_budget(db, messages)

    llm_start = time.monotonic()
    report = await client.complete(messages)
    llm_duration = time.monotonic() - llm_start
    logger.info(
        "LLM call completed in %.2fs (provider=%s model=%s)",
        llm_duration,
        settings.llm_provider,
        getattr(client, "model", "unknown"),
    )

    usage = client.last_usage or {}
    if usage.get("input_tokens") is None:
        usage["input_tokens"] = cost_tracker.estimate_input_tokens(messages)
    if usage.get("output_tokens") is None and report:
        usage["output_tokens"] = cost_tracker.estimate_text_tokens(report)

    cost = cost_tracker.compute_cost(usage)
    await record_event(
        db,
        report_event_type,
        request,
        region,
        tokens_input=usage.get("input_tokens"),
        tokens_output=usage.get("output_tokens"),
        cost_cny=cost,
    )

    return report, usage, client.metadata, cost
