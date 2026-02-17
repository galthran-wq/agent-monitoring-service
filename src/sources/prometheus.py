import httpx
import structlog

from src.config import settings
from src.sources.base import BaseSource, SourceData

logger = structlog.get_logger()

BUILTIN_QUERIES = [
    ("Service Up", "up"),
    ("Request Rate (5m)", "sum(rate(http_requests_total[5m])) by (job)"),
    ("Error Rate 5xx (5m)", "sum(rate(http_requests_total{status=~'5..'}[5m])) by (job)"),
    ("P95 Latency", "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job))"),
    ("P99 Latency", "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job))"),
]


class PrometheusSource(BaseSource):
    name = "prometheus"

    def is_configured(self) -> bool:
        return settings.prometheus_enabled and bool(settings.prometheus_url)

    async def fetch(self, lookback_seconds: int) -> SourceData:
        queries = [*BUILTIN_QUERIES]
        for extra in settings.prometheus_extra_queries:
            queries.append((extra, extra))

        sections: list[str] = []
        down_services: list[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for label, query in queries:
                try:
                    resp = await client.get(
                        f"{settings.prometheus_url}/api/v1/query",
                        params={"query": query},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    results = data.get("data", {}).get("result", [])
                    lines: list[str] = []
                    for result in results:
                        metric = result.get("metric", {})
                        value = result.get("value", [None, None])
                        metric_str = ", ".join(f"{k}={v}" for k, v in metric.items())
                        lines.append(f"  {metric_str}: {value[1]}")

                        if label == "Service Up" and value[1] == "0":
                            job = metric.get("job", metric_str)
                            down_services.append(job)

                    section = f"{label} ({query}):\n" + ("\n".join(lines) if lines else "  no data")
                    sections.append(section)

                except Exception as e:
                    logger.warning("prometheus_query_error", query=query, error=str(e))
                    sections.append(f"{label} ({query}):\n  Error: {e}")

        raw_text = "\n\n".join(sections)
        summary = f"Down services: {down_services}" if down_services else "All services up"

        return SourceData(source_name=self.name, summary=summary, raw_text=raw_text)
