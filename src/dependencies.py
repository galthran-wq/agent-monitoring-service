from typing import Annotated

from fastapi import Depends, Request

from src.services.monitor import AgentMonitor


def get_monitor(request: Request) -> AgentMonitor:
    return request.app.state.monitor  # type: ignore[no-any-return]


MonitorDep = Annotated[AgentMonitor, Depends(get_monitor)]
