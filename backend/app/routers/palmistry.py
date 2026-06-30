from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Request, Depends
from typing import Optional
import logging

from app.models.palmistry import PalmistryResponse
from app.config import settings
from app.db import get_db_optional
from app.services.providers.openai_compatible_provider import create_llm_client
from app.services.prompt_manager import prompt_manager
from app.services.image_processor import ImageProcessor
from app.services.text_cleaner import clean_report
from app.services.analytics import EVENT_PALMISTRY_REQUEST, EVENT_PALMISTRY_REPORT
from app.services.llm_guard import complete_with_guard


router = APIRouter()
logger = logging.getLogger(__name__)


VALID_GENDERS = {"male", "female", "男", "女"}
VALID_HANDS = {"left", "right", "左手", "右手"}


@router.post("/palmistry", response_model=PalmistryResponse)
async def analyze_palmistry(
    request: Request,
    hand_image: UploadFile = File(...),
    gender: str = Form(...),
    dominant_hand: str = Form(...),
    uploaded_hand: str = Form(...),
    x_region: Optional[str] = Header(default=None),
    db: Optional = Depends(get_db_optional),
):
    if gender not in VALID_GENDERS:
        raise HTTPException(status_code=400, detail="Invalid gender value.")
    if dominant_hand not in VALID_HANDS:
        raise HTTPException(status_code=400, detail="Invalid dominant_hand value.")
    if uploaded_hand not in VALID_HANDS:
        raise HTTPException(status_code=400, detail="Invalid uploaded_hand value.")

    region = x_region if x_region in {"cn", "eu", "us"} else "global"

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

        report, usage, metadata, cost = await complete_with_guard(
            request=request,
            db=db,
            region=region,
            client=client,
            messages=normalized,
            request_event_type=EVENT_PALMISTRY_REQUEST,
            report_event_type=EVENT_PALMISTRY_REPORT,
        )

        cleaned_report = clean_report(report)
        return PalmistryResponse(report=cleaned_report, metadata={**metadata, "cost_cny": float(cost)})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Palmistry analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again later.")
