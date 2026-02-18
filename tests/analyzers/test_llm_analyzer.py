from unittest.mock import AsyncMock, patch

from src.analyzers.llm_analyzer import _build_fallback_report, _truncate_to_budget, analyze
from src.sources.base import SourceData


def test_truncate_to_budget_fits():
    data = [SourceData(source_name="test", summary="ok", raw_text="short log")]
    result = _truncate_to_budget(data, max_tokens=1000)
    assert "short log" in result
    assert "truncated" not in result


def test_truncate_to_budget_truncates():
    data = [SourceData(source_name="test", summary="ok", raw_text="x" * 100000)]
    result = _truncate_to_budget(data, max_tokens=100)
    assert "truncated" in result


def test_fallback_report():
    data = [
        SourceData(source_name="loki", summary="Errors: 5", raw_text="..."),
        SourceData(source_name="prometheus", summary="All ok", raw_text="..."),
    ]
    report = _build_fallback_report(data)
    assert "fallback" in report.lower()
    assert "Errors: 5" in report
    assert "All ok" in report


async def test_analyze_with_llm(monkeypatch: object):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "test-key")  # type: ignore[attr-defined]

    mock_message = AsyncMock()
    mock_message.content = "**Overall Status**: 🟢 Healthy"

    mock_choice = AsyncMock()
    mock_choice.message = mock_message

    mock_response = AsyncMock()
    mock_response.choices = [mock_choice]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.analyzers.llm_analyzer._build_client", return_value=mock_client):
        data = [SourceData(source_name="test", summary="ok", raw_text="all good")]
        result = await analyze(data)

    assert "Healthy" in result


async def test_analyze_falls_back_on_error(monkeypatch: object):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "test-key")  # type: ignore[attr-defined]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=ConnectionError("down"))

    with patch("src.analyzers.llm_analyzer._build_client", return_value=mock_client):
        data = [SourceData(source_name="test", summary="ok", raw_text="all good")]
        result = await analyze(data)

    assert "fallback" in result.lower()


async def test_analyze_without_api_key(monkeypatch: object):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "")  # type: ignore[attr-defined]

    data = [SourceData(source_name="test", summary="ok", raw_text="all good")]
    result = await analyze(data)
    assert "fallback" in result.lower()
