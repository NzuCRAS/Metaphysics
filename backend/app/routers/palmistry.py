from fastapi import APIRouter, Form, UploadFile, File, HTTPException
import logging

from app.models.palmistry import PalmistryResponse
from app.config import settings
from app.services.providers.openai_compatible_provider import create_llm_client
from app.services.prompt_manager import prompt_manager
from app.services.image_processor import ImageProcessor
from app.services.text_cleaner import clean_report


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/palmistry", response_model=PalmistryResponse)
async def analyze_palmistry(
    hand_image: UploadFile = File(...),
    gender: str = Form(...),
    dominant_hand: str = Form(...),
    uploaded_hand: str = Form(...),
):
    try:
        client = create_llm_client(settings)
        base64_image, mime_type = await ImageProcessor.process(hand_image)

        prompt = prompt_manager.get_palmistry_prompt()
        messages = prompt.format_messages(
            gender=gender,
            dominant_hand=dominant_hand,
            uploaded_hand=uploaded_hand,
        )

        # 转换为 LLMClient 统一格式，并附加图片
        normalized = [{"role": "system", "content": messages[0].content}]
        for msg in messages[1:]:
            role = "human" if msg.type == "human" else "ai"
            normalized.append({"role": role, "content": msg.content})

        normalized = prompt_manager.attach_image_to_human(normalized, base64_image, mime_type)

        report = await client.complete(normalized)
        cleaned_report = clean_report(report)
        return PalmistryResponse(report=cleaned_report, metadata=client.metadata)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Palmistry analysis failed")
        raise HTTPException(status_code=500, detail=f"LLM invocation failed: {str(e)}")
