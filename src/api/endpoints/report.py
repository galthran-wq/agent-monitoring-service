import asyncio

from fastapi import APIRouter

from src.dependencies import MonitorDep
from src.schemas.report import ReportResponse, TriggerResponse

router = APIRouter()


@router.get("/report")
async def get_last_report(monitor: MonitorDep) -> ReportResponse:
    return ReportResponse(
        report=monitor.last_report,
        generated_at=monitor.last_report_at,
    )


@router.post("/trigger", status_code=202)
async def trigger_report(monitor: MonitorDep) -> TriggerResponse:
    if monitor.running:
        return TriggerResponse(status="already_running")
    asyncio.create_task(monitor.tick())
    return TriggerResponse(status="started")
