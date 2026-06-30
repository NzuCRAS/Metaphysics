import ipaddress
import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent


logger = logging.getLogger(__name__)

EVENT_PAGEVIEW = "pageview"
EVENT_BAZI_REQUEST = "bazi_request"
EVENT_BAZI_REPORT = "bazi_report"
EVENT_PALMISTRY_REQUEST = "palmistry_request"
EVENT_PALMISTRY_REPORT = "palmistry_report"


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _get_client_ip(request: Request) -> str:
    """优先从反向代理头获取真实 IP，并对值做基础校验，防止日志注入。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if _is_valid_ip(candidate):
            return candidate
    real_ip = request.headers.get("x-real-ip")
    if real_ip and _is_valid_ip(real_ip.strip()):
        return real_ip.strip()
    if request.client and request.client.host and _is_valid_ip(request.client.host):
        return request.client.host
    return "unknown"


def _validate_region(region: Optional[str]) -> str:
    if region in {"cn", "eu", "us"}:
        return region
    return "global"


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


async def record_event(
    session: AsyncSession,
    event_type: str,
    request: Request,
    region: Optional[str] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    cost_cny: Optional[Decimal] = None,
) -> AnalyticsEvent:
    event = AnalyticsEvent(
        event_type=event_type,
        region=_validate_region(region),
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:500],
        path=request.url.path[:500],
        timestamp=datetime.now(timezone.utc),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_cny=cost_cny,
    )
    session.add(event)
    await session.commit()
    return event


async def today_cost(session: AsyncSession) -> Decimal:
    """Today UTC 已产生的 bazi_report 实际花费。"""
    start, end = _day_bounds(date.today())
    result = await session.execute(
        select(func.coalesce(func.sum(AnalyticsEvent.cost_cny), 0)).where(
            AnalyticsEvent.event_type == EVENT_BAZI_REPORT,
            AnalyticsEvent.timestamp >= start,
            AnalyticsEvent.timestamp < end,
        )
    )
    return Decimal(result.scalar_one())


async def get_daily_summary(session: AsyncSession, day: date) -> dict:
    start, end = _day_bounds(day)

    rows = await session.execute(
        select(AnalyticsEvent).where(
            AnalyticsEvent.timestamp >= start, AnalyticsEvent.timestamp < end
        )
    )
    events = rows.scalars().all()

    total_pageviews = sum(1 for e in events if e.event_type == EVENT_PAGEVIEW)
    total_requests = sum(1 for e in events if e.event_type == EVENT_BAZI_REQUEST)
    total_reports = sum(1 for e in events if e.event_type == EVENT_BAZI_REPORT)
    total_palmistry_requests = sum(1 for e in events if e.event_type == EVENT_PALMISTRY_REQUEST)
    total_palmistry_reports = sum(1 for e in events if e.event_type == EVENT_PALMISTRY_REPORT)
    total_cost = sum(
        ((e.cost_cny or Decimal("0")) for e in events if e.event_type in (EVENT_BAZI_REPORT, EVENT_PALMISTRY_REPORT)),
        Decimal("0"),
    )
    unique_ips = len({e.ip_address for e in events if e.event_type == EVENT_PAGEVIEW})

    by_region: dict = {}
    cost_by_region: dict = {}
    for ev in events:
        by_region.setdefault(ev.region, {}).setdefault(ev.event_type, 0)
        by_region[ev.region][ev.event_type] += 1
        if ev.event_type == EVENT_BAZI_REPORT and ev.cost_cny:
            cost_by_region[ev.region] = cost_by_region.get(ev.region, Decimal("0")) + ev.cost_cny

    hourly_map: dict = {}
    half_map: dict = {}
    for ev in events:
        ts = ev.timestamp
        hour_key = f"{ts.hour:02d}:00"
        hourly_map.setdefault(hour_key, {})
        hourly_map[hour_key].setdefault(ev.event_type, 0)
        hourly_map[hour_key][ev.event_type] += 1

        minute_slot = 0 if ts.minute < 30 else 30
        half_key = f"{ts.hour:02d}:{minute_slot:02d}"
        half_map.setdefault(half_key, {})
        half_map[half_key].setdefault(ev.event_type, 0)
        half_map[half_key][ev.event_type] += 1

    hourly_list = [{"hour": k, **v} for k, v in sorted(hourly_map.items())]
    half_list = [{"slot": k, **v} for k, v in sorted(half_map.items())]

    return {
        "date": day.isoformat(),
        "total_pageviews": total_pageviews,
        "total_bazi_requests": total_requests,
        "total_bazi_reports": total_reports,
        "total_palmistry_requests": total_palmistry_requests,
        "total_palmistry_reports": total_palmistry_reports,
        "total_cost_cny": float(total_cost.quantize(Decimal("0.000001"))),
        "unique_ips": unique_ips,
        "by_region": by_region,
        "cost_by_region": {
            k: float(v.quantize(Decimal("0.000001")))
            for k, v in sorted(cost_by_region.items())
        },
        "hourly": hourly_list,
        "half_hourly": half_list,
    }


async def get_daily_events(
    session: AsyncSession, day: date, limit: int = 200, offset: int = 0
):
    """返回指定日期的事件明细，支持分页。"""
    start, end = _day_bounds(day)
    rows = await session.execute(
        select(AnalyticsEvent)
        .where(AnalyticsEvent.timestamp >= start, AnalyticsEvent.timestamp < end)
        .order_by(AnalyticsEvent.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    return rows.scalars().all()


async def get_daily_report_text(session: AsyncSession, day: date) -> str:
    start, end = _day_bounds(day)

    rows = await session.execute(
        select(AnalyticsEvent)
        .where(AnalyticsEvent.timestamp >= start, AnalyticsEvent.timestamp < end)
        .order_by(AnalyticsEvent.timestamp)
    )
    events = rows.scalars().all()

    summary = await get_daily_summary(session, day)

    lines = [
        f"Metaphysics Traffic Report - {day.isoformat()} UTC",
        "=" * 60,
        "",
        "Summary",
        f"  Page views:        {summary['total_pageviews']}",
        f"  BaZi requests:     {summary['total_bazi_requests']}",
        f"  BaZi reports:      {summary['total_bazi_reports']}",
        f"  Total LLM cost:    {summary['total_cost_cny']:.6f} CNY",
        "",
        "By Region",
    ]
    for region, counts in sorted(summary["by_region"].items()):
        parts = " | ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"  {region}: {parts}")

    lines.extend([
        "",
        "Hourly Breakdown",
    ])
    for bucket in summary["hourly"]:
        lines.append(
            f"  {bucket['hour']}  PV={bucket.get(EVENT_PAGEVIEW, 0)} "
            f"REQ={bucket.get(EVENT_BAZI_REQUEST, 0)} "
            f"RPT={bucket.get(EVENT_BAZI_REPORT, 0)}"
        )

    lines.extend([
        "",
        "30-Minute Breakdown",
    ])
    for bucket in summary["half_hourly"]:
        lines.append(
            f"  {bucket['slot']}  PV={bucket.get(EVENT_PAGEVIEW, 0)} "
            f"REQ={bucket.get(EVENT_BAZI_REQUEST, 0)} "
            f"RPT={bucket.get(EVENT_BAZI_REPORT, 0)}"
        )

    lines.extend([
        "",
        "Detail Log",
        "-" * 60,
    ])
    for ev in events:
        cost = f"{ev.cost_cny:.6f}" if ev.cost_cny is not None else "-"
        tokens = ""
        if ev.tokens_input is not None and ev.tokens_output is not None:
            tokens = f" in={ev.tokens_input} out={ev.tokens_output}"
        lines.append(
            f"{ev.timestamp.isoformat()}  {ev.event_type:15s}  "
            f"region={ev.region:6s}  ip={ev.ip_address:15s}  "
            f"path={ev.path}{tokens}  cost={cost}"
        )

    lines.append("")
    return "\n".join(lines)
