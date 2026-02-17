import asyncio
from datetime import UTC, datetime

import structlog

from src.analyzers import llm_analyzer
from src.config import settings
from src.exporters.base import BaseExporter
from src.sources.base import BaseSource, SourceData

logger = structlog.get_logger()


class AgentMonitor:
    def __init__(
        self,
        sources: list[BaseSource],
        exporters: list[BaseExporter],
    ) -> None:
        self._sources = sources
        self._exporters = exporters
        self._last_report: str | None = None
        self._last_report_at: datetime | None = None

    @property
    def last_report(self) -> str | None:
        return self._last_report

    @property
    def last_report_at(self) -> datetime | None:
        return self._last_report_at

    async def _fetch_all(self) -> list[SourceData]:
        tasks = {s.name: s.fetch(settings.lookback_period) for s in self._sources}
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

        results: list[SourceData] = []
        for name, result in zip(tasks.keys(), gathered, strict=True):
            if isinstance(result, BaseException):
                logger.warning("source_fetch_error", source=name, error=str(result))
                results.append(SourceData(source_name=name, summary=f"Error: {result}", raw_text=""))
            else:
                results.append(result)
        return results

    async def _analyze(self, source_data: list[SourceData]) -> str:
        return await llm_analyzer.analyze(source_data)

    async def _export_all(self, report: str) -> None:
        for exporter in self._exporters:
            try:
                await exporter.export(report)
            except Exception as e:
                logger.error("exporter_error", exporter=exporter.name, error=str(e))

    async def tick(self) -> None:
        source_data = await self._fetch_all()
        report = await self._analyze(source_data)
        self._last_report = report
        self._last_report_at = datetime.now(UTC)
        await self._export_all(report)
        logger.info("monitor_tick_complete", sources=[s.source_name for s in source_data])

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as e:
                logger.error("monitor_loop_error", error=str(e))
            await asyncio.sleep(settings.monitor_interval)
