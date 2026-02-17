from src.sources.base import BaseSource
from src.sources.loki import LokiSource
from src.sources.prometheus import PrometheusSource

ALL_SOURCES: list[type[BaseSource]] = [
    LokiSource,
    PrometheusSource,
]


def get_configured_sources() -> list[BaseSource]:
    sources: list[BaseSource] = []
    for cls in ALL_SOURCES:
        instance = cls()
        if instance.is_configured():
            sources.append(instance)
    return sources
