import respx
from httpx import Response
from src.sources.prometheus import PrometheusSource


async def test_prometheus_fetch_parses_results():
    prom_response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"job": "server", "__name__": "up"}, "value": [1700000000, "1"]},
            ],
        },
    }

    source = PrometheusSource()

    with respx.mock:
        respx.get("http://prometheus:9090/api/v1/query").mock(return_value=Response(200, json=prom_response))

        result = await source.fetch(lookback_seconds=3600)

    assert result.source_name == "prometheus"
    assert "All services up" in result.summary
    assert "server" in result.raw_text


async def test_prometheus_detects_down_services():
    prom_up_response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"job": "server", "__name__": "up"}, "value": [1700000000, "0"]},
            ],
        },
    }
    prom_empty = {
        "status": "success",
        "data": {"resultType": "vector", "result": []},
    }

    source = PrometheusSource()

    with respx.mock:
        route = respx.get("http://prometheus:9090/api/v1/query")
        # First call is for "up" query, rest return empty
        route.side_effect = [
            Response(200, json=prom_up_response),
            Response(200, json=prom_empty),
            Response(200, json=prom_empty),
            Response(200, json=prom_empty),
            Response(200, json=prom_empty),
        ]

        result = await source.fetch(lookback_seconds=3600)

    assert "server" in result.summary
    assert "Down services" in result.summary


async def test_prometheus_handles_connection_error():
    source = PrometheusSource()

    with respx.mock:
        respx.get("http://prometheus:9090/api/v1/query").mock(side_effect=ConnectionError("refused"))

        result = await source.fetch(lookback_seconds=3600)

    assert result.source_name == "prometheus"
    assert "Error" in result.raw_text
