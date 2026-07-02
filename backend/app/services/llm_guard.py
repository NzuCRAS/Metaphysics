import logging
import time
from decimal import Decimal
from typing import Optional
import json

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


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_with_guard(
    request: Request,
    db: Optional[AsyncSession],
    region: str,
    client,
    messages: list[dict],
    request_event_type: str,
    report_event_type: str,
):
    """统一封装 LLM 流式调用：记录请求、检查预算、流式生成、记录报告与成本。

    产生 SSE 数据行（包括 chunk / done / error）。
    """
    if db is None:
        logger.error("LLM stream attempted while analytics database is unavailable")
        yield _format_sse({"type": "error", "message": "Cost tracking database is not available; LLM calls are disabled."})
        return

    await record_event(db, request_event_type, request, region)

    try:
        await cost_tracker.check_budget(db, messages)
    except HTTPException as exc:
        if exc.status_code == 429:
            yield _format_sse({"type": "error", "message": "今天的服务已经结束啦，请明天再来"})
        else:
            yield _format_sse({"type": "error", "message": str(exc.detail)})
        return

    llm_start = time.monotonic()
    first_chunk_time: Optional[float] = None
    accumulated_text = ""
    chunk_count = 0

    try:
        async for delta in client.stream(messages):
            if first_chunk_time is None:
                first_chunk_time = time.monotonic() - llm_start
            if delta:
                accumulated_text += delta
                chunk_count += 1
                yield _format_sse({"type": "chunk", "delta": delta})
    except Exception as e:
        logger.exception("LLM stream failed")
        yield _format_sse({"type": "error", "message": "Analysis failed. Please try again later."})
        return

    stream_duration = time.monotonic() - llm_start
    logger.info(
        "LLM stream finished in %.2fs (first_chunk=%.2fs, chunks=%d, provider=%s, model=%s)",
        stream_duration,
        first_chunk_time or 0.0,
        chunk_count,
        settings.llm_provider,
        getattr(client, "model", "unknown"),
    )

    usage = client.last_usage or {}
    if usage.get("input_tokens") is None:
        usage["input_tokens"] = cost_tracker.estimate_input_tokens(messages)
    if usage.get("output_tokens") is None and accumulated_text:
        usage["output_tokens"] = cost_tracker.estimate_text_tokens(accumulated_text)

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

    yield _format_sse({
        "type": "done",
        "metadata": {**client.metadata, "cost_cny": float(cost)},
    })
