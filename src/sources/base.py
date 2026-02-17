from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SourceData:
    source_name: str
    summary: str
    raw_text: str


class BaseSource(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def fetch(self, lookback_seconds: int) -> SourceData: ...
