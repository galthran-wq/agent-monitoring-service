import respx
from httpx import Response
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


async def test_analyze_with_llm(monkeypatch):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "test-key")
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_base_url", "https://api.test.com/v1")

    data = [SourceData(source_name="test", summary="ok", raw_text="all good")]

    with respx.mock:
        respx.post("https://api.test.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={"choices": [{"message": {"content": "**Overall Status**: 🟢 Healthy"}}]},
            )
        )

        result = await analyze(data)

    assert "Healthy" in result


async def test_analyze_falls_back_on_error(monkeypatch):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "test-key")
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_base_url", "https://api.test.com/v1")

    data = [SourceData(source_name="test", summary="ok", raw_text="all good")]

    with respx.mock:
        respx.post("https://api.test.com/v1/chat/completions").mock(side_effect=ConnectionError("down"))

        result = await analyze(data)

    assert "fallback" in result.lower()


async def test_analyze_without_api_key(monkeypatch):
    monkeypatch.setattr("src.analyzers.llm_analyzer.settings.llm_api_key", "")

    data = [SourceData(source_name="test", summary="ok", raw_text="all good")]
    result = await analyze(data)
    assert "fallback" in result.lower()
