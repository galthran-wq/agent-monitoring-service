from datetime import datetime

from pydantic import BaseModel


class ReportResponse(BaseModel):
    report: str | None
    generated_at: datetime | None


class TriggerResponse(BaseModel):
    status: str
