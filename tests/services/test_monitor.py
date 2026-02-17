from unittest.mock import AsyncMock, patch

from src.services.monitor import AgentMonitor
from src.sources.base import SourceData


async def test_monitor_tick():
    mock_source = AsyncMock()
    mock_source.name = "test_source"
    mock_source.fetch.return_value = SourceData(source_name="test_source", summary="ok", raw_text="all good")

    mock_exporter = AsyncMock()
    mock_exporter.name = "test_exporter"

    monitor = AgentMonitor(sources=[mock_source], exporters=[mock_exporter])

    with patch("src.services.monitor.llm_analyzer") as mock_analyzer:
        mock_analyzer.analyze = AsyncMock(return_value="Test report content")
        await monitor.tick()

    assert monitor.last_report == "Test report content"
    assert monitor.last_report_at is not None
    mock_exporter.export.assert_called_once_with("Test report content")


async def test_monitor_tick_handles_source_error():
    mock_source = AsyncMock()
    mock_source.name = "failing_source"
    mock_source.fetch.side_effect = ConnectionError("down")

    mock_exporter = AsyncMock()
    mock_exporter.name = "test_exporter"

    monitor = AgentMonitor(sources=[mock_source], exporters=[mock_exporter])

    with patch("src.services.monitor.llm_analyzer") as mock_analyzer:
        mock_analyzer.analyze = AsyncMock(return_value="Error report")
        await monitor.tick()

    assert monitor.last_report == "Error report"
    mock_exporter.export.assert_called_once()


async def test_monitor_tick_handles_exporter_error():
    mock_source = AsyncMock()
    mock_source.name = "test_source"
    mock_source.fetch.return_value = SourceData(source_name="test_source", summary="ok", raw_text="all good")

    mock_exporter = AsyncMock()
    mock_exporter.name = "failing_exporter"
    mock_exporter.export.side_effect = ConnectionError("telegram down")

    monitor = AgentMonitor(sources=[mock_source], exporters=[mock_exporter])

    with patch("src.services.monitor.llm_analyzer") as mock_analyzer:
        mock_analyzer.analyze = AsyncMock(return_value="Test report")
        # Should not raise
        await monitor.tick()

    assert monitor.last_report == "Test report"
