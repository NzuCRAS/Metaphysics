from fastapi import APIRouter, HTTPException
import logging

from app.models.bazi import BaziRequest, BaziResponse
from app.config import settings
from app.services.providers.openai_compatible_provider import create_llm_client
from app.services.prompt_manager import prompt_manager
from app.services.text_cleaner import clean_report


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/bazi", response_model=BaziResponse)
async def analyze_bazi(request: BaziRequest):
    try:
        client = create_llm_client(settings)
        prompt = prompt_manager.get_bazi_prompt()

        messages = prompt.format_messages(
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            gender=request.gender,
            birthplace=request.birthplace,
        )

        # 转换为 LLMClient 统一格式
        normalized = [{"role": "system", "content": messages[0].content}]
        for msg in messages[1:]:
            role = "human" if msg.type == "human" else "ai"
            normalized.append({"role": role, "content": msg.content})

        report = await client.complete(normalized)
        cleaned_report = clean_report(report)
        return BaziResponse(report=cleaned_report, metadata=client.metadata)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bazi analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again later.")
