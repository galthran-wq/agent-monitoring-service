from fastapi import APIRouter

from src.dependencies import MonitorDep
from src.schemas.report import ReportResponse

router = APIRouter()


@router.get("/report")
async def get_last_report(monitor: MonitorDep) -> ReportResponse:
    return ReportResponse(
        report=monitor.last_report,
        generated_at=monitor.last_report_at,
    )
