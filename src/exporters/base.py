from abc import ABC, abstractmethod


class BaseExporter(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def export(self, report: str) -> None: ...
