from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from src.main import app
from src.services.monitor import AgentMonitor


async def test_trigger_starts_tick():
    monitor = AgentMonitor(sources=[], exporters=[])
    app.state.monitor = monitor

    with patch.object(monitor, "tick", new_callable=AsyncMock) as mock_tick:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/trigger")

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "started"
    mock_tick.assert_called_once()


async def test_trigger_already_running():
    monitor = AgentMonitor(sources=[], exporters=[])
    monitor._running = True
    app.state.monitor = monitor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/trigger")

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "already_running"
