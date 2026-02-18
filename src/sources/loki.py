import time

import httpx
import structlog

from src.config import settings
from src.sources.base import BaseSource, SourceData

logger = structlog.get_logger()

MAX_LOG_LINE_CHARS = 500
MAX_ERROR_LOGS = 50


class LokiSource(BaseSource):
    name = "loki"

    def is_configured(self) -> bool:
        return settings.loki_enabled and bool(settings.loki_url)

    async def fetch(self, lookback_seconds: int) -> SourceData:
        now_ns = int(time.time() * 1e9)
        start_ns = now_ns - int(lookback_seconds * 1e9)

        queries = [
            '{level=~"error|ERROR|fatal|FATAL"}',
            '{level=~"warning|WARNING"}',
            '{detected_level=~"error|ERROR|fatal|FATAL"}',
            '{detected_level=~"warning|WARNING"}',
            *settings.loki_extra_queries,
        ]

        sections: list[str] = []
        error_count = 0
        warning_count = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for query in queries:
                try:
                    resp = await client.get(
                        f"{settings.loki_url}/loki/api/v1/query_range",
                        params={
                            "query": query,
                            "start": str(start_ns),
                            "end": str(now_ns),
                            "limit": str(MAX_ERROR_LOGS),
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    lines: list[str] = []
                    for stream in data.get("data", {}).get("result", []):
                        labels = stream.get("stream", {})
                        label_str = ", ".join(f"{k}={v}" for k, v in labels.items())
                        for _ts, line in stream.get("values", []):
                            truncated = line[:MAX_LOG_LINE_CHARS]
                            lines.append(f"[{label_str}] {truncated}")

                    if "error" in query.lower() or "fatal" in query.lower():
                        error_count += len(lines)
                    elif "warning" in query.lower():
                        warning_count += len(lines)

                    if lines:
                        sections.append(f"Query: {query}\n" + "\n".join(lines[:MAX_ERROR_LOGS]))

                except Exception as e:
                    logger.warning("loki_query_error", query=query, error=str(e))
                    sections.append(f"Query: {query}\nError fetching: {e}")

        raw_text = "\n\n".join(sections) if sections else "No log entries found."
        summary = f"Errors: {error_count}, Warnings: {warning_count}"

        return SourceData(source_name=self.name, summary=summary, raw_text=raw_text)
