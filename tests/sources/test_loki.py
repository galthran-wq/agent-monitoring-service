import respx
from httpx import Response
from src.sources.loki import LokiSource


async def test_loki_fetch_parses_streams():
    error_response = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"level": "error", "job": "server"},
                    "values": [
                        ["1700000000000000000", "Connection refused to database"],
                        ["1700000001000000000", "Timeout on request /api/chat"],
                    ],
                }
            ],
        },
    }
    empty_response = {"status": "success", "data": {"resultType": "streams", "result": []}}

    source = LokiSource()

    call_count = 0

    def _route_handler(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(200, json=error_response)
        return Response(200, json=empty_response)

    with respx.mock:
        respx.get("http://loki:3100/loki/api/v1/query_range").mock(side_effect=_route_handler)

        result = await source.fetch(lookback_seconds=3600)

    assert result.source_name == "loki"
    assert "Errors: 2" in result.summary
    assert "Connection refused" in result.raw_text
    assert "Timeout on request" in result.raw_text


async def test_loki_fetch_handles_empty_result():
    loki_response = {
        "status": "success",
        "data": {"resultType": "streams", "result": []},
    }

    source = LokiSource()

    with respx.mock:
        respx.get("http://loki:3100/loki/api/v1/query_range").mock(return_value=Response(200, json=loki_response))

        result = await source.fetch(lookback_seconds=3600)

    assert result.source_name == "loki"
    assert "Errors: 0" in result.summary


async def test_loki_fetch_handles_connection_error():
    source = LokiSource()

    with respx.mock:
        respx.get("http://loki:3100/loki/api/v1/query_range").mock(side_effect=ConnectionError("refused"))

        result = await source.fetch(lookback_seconds=3600)

    assert result.source_name == "loki"
    assert "Error fetching" in result.raw_text


async def test_loki_is_configured(monkeypatch):
    monkeypatch.setattr("src.sources.loki.settings.loki_enabled", True)
    monkeypatch.setattr("src.sources.loki.settings.loki_url", "http://loki:3100")
    assert LokiSource().is_configured() is True

    monkeypatch.setattr("src.sources.loki.settings.loki_enabled", False)
    assert LokiSource().is_configured() is False
