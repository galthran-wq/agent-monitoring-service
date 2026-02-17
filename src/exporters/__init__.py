from src.exporters.base import BaseExporter
from src.exporters.telegram import TelegramExporter

ALL_EXPORTERS: list[type[BaseExporter]] = [
    TelegramExporter,
]


def get_configured_exporters() -> list[BaseExporter]:
    exporters: list[BaseExporter] = []
    for cls in ALL_EXPORTERS:
        instance = cls()
        if instance.is_configured():
            exporters.append(instance)
    return exporters
