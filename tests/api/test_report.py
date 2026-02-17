from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from src.main import app
from src.services.monitor import AgentMonitor


async def test_report_endpoint_no_report():
    monitor = AgentMonitor(sources=[], exporters=[])
    app.state.monitor = monitor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/report")

    assert resp.status_code == 200
    data = resp.json()
    assert data["report"] is None
    assert data["generated_at"] is None


async def test_report_endpoint_with_report():
    monitor = AgentMonitor(sources=[], exporters=[])
    monitor._last_report = "Test report"
    monitor._last_report_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    app.state.monitor = monitor

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/report")

    assert resp.status_code == 200
    data = resp.json()
    assert data["report"] == "Test report"
    assert data["generated_at"] is not None
