import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics import today_cost


logger = logging.getLogger(__name__)


def _token_str(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    # 图片不计入文本 token，用一个很小的占位避免低估
                    parts.append("[image]")
        return " ".join(parts)
    return str(value)


class CostTracker:
    def __init__(
        self,
        input_price_per_m: float,
        output_price_per_m: float,
        max_daily_cny: float,
        max_output_tokens: int,
        safety_factor: float = 1.5,
    ):
        self.input_price = Decimal(str(input_price_per_m))
        self.output_price = Decimal(str(output_price_per_m))
        self.max_daily = Decimal(str(max_daily_cny))
        self.max_output_tokens = max_output_tokens
        self.safety_factor = safety_factor

    def estimate_text_tokens(self, text: str) -> int:
        """离线环境下的保守兜底：按 1 token ≈ 2 个字符估算。"""
        return max(1, int(len(_token_str(text)) / 2))

    def estimate_input_tokens(self, messages: list[dict]) -> int:
        """保守估算 prompt tokens：字符数 / 2 * 安全系数。

        不依赖外部 tokenizer，确保离线环境可用且不会低估。
        """
        text = " ".join(_token_str(m.get("content", "")) for m in messages)
        return int(len(text) / 2 * self.safety_factor)

    def estimate_max_cost(self, messages: list[dict]) -> Decimal:
        input_tokens = self.estimate_input_tokens(messages)
        input_cost = Decimal(input_tokens) * self.input_price / Decimal("1_000_000")
        output_cost = Decimal(self.max_output_tokens) * self.output_price / Decimal("1_000_000")
        return (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    def compute_cost(self, usage: dict) -> Decimal:
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        input_cost = Decimal(input_tokens) * self.input_price / Decimal("1_000_000")
        output_cost = Decimal(output_tokens) * self.output_price / Decimal("1_000_000")
        return (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    async def today_cost(self, session: AsyncSession) -> Decimal:
        return await today_cost(session)

    async def check_budget(
        self,
        session: AsyncSession,
        messages: list[dict],
    ) -> None:
        """在真正调用 LLM 前检查预算。若会超支则抛出 429。"""
        spent = await self.today_cost(session)
        if spent >= self.max_daily:
            logger.warning("Daily LLM budget already exhausted: %s / %s CNY", spent, self.max_daily)
            raise HTTPException(
                status_code=429,
                detail="Daily report quota has been reached. Please try again tomorrow.",
            )

        estimated = self.estimate_max_cost(messages)
        if spent + estimated > self.max_daily:
            logger.warning(
                "Daily LLM budget would be exceeded: spent=%s estimated=%s max=%s",
                spent, estimated, self.max_daily
            )
            raise HTTPException(
                status_code=429,
                detail="Daily report quota has been reached. Please try again tomorrow.",
            )
