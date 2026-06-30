from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db_optional
from app.services.analytics import (
    EVENT_PAGEVIEW,
    get_daily_summary,
    get_daily_report_text,
    record_event,
)


router = APIRouter()


def _region(header: Optional[str]) -> str:
    if header in {"cn", "eu", "us"}:
        return header
    return "global"


def _verify_admin_token(token: str) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin token is not configured")
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/analytics/pageview")
async def pageview(
    request: Request,
    x_region: Optional[str] = Header(default=None),
    db: Optional[AsyncSession] = Depends(get_db_optional),
):
    region = _region(x_region)
    if db is not None:
        await record_event(db, EVENT_PAGEVIEW, request, region)
    return {"ok": True, "region": region}


@router.get("/admin/traffic-summary")
async def traffic_summary(
    request: Request,
    date_param: date = Query(..., alias="date"),
    token: str = Query(...),
    db: Optional[AsyncSession] = Depends(get_db_optional),
):
    _verify_admin_token(token)
    if db is None:
        raise HTTPException(status_code=503, detail="Analytics database is not configured")
    summary = await get_daily_summary(db, date_param)
    return summary


@router.get("/admin/traffic-report")
async def traffic_report(
    request: Request,
    date_param: date = Query(..., alias="date"),
    token: str = Query(...),
    db: Optional[AsyncSession] = Depends(get_db_optional),
):
    _verify_admin_token(token)
    if db is None:
        raise HTTPException(status_code=503, detail="Analytics database is not configured")
    text = await get_daily_report_text(db, date_param)
    filename = f"traffic_{date_param.isoformat()}.txt"
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
