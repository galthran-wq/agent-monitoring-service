from datetime import UTC, datetime

import httpx
import structlog

from src.config import settings
from src.exporters.base import BaseExporter

logger = structlog.get_logger()

TG_API = "https://api.telegram.org/bot{token}"
TG_MAX_MESSAGE_LENGTH = 4096


def _find_split_point(text: str, max_length: int) -> int:
    candidate = text[:max_length]
    idx = candidate.rfind("\n")
    if idx > max_length // 2:
        return idx + 1
    idx = candidate.rfind(" ")
    if idx > max_length // 2:
        return idx + 1
    amp_idx = candidate.rfind("&")
    if amp_idx != -1 and ";" not in candidate[amp_idx:]:
        return amp_idx
    return max_length


def _format_messages(report: str) -> list[str]:
    ts = datetime.now(UTC).strftime("%H:%M %d.%m.%Y")
    header = f"<b>Agent Monitoring Report</b> ({ts})\n\n"
    body = report

    first_limit = TG_MAX_MESSAGE_LENGTH - len(header)

    if len(body) <= first_limit:
        return [header + body]

    messages: list[str] = []
    remaining = body
    is_first = True

    while remaining:
        limit = first_limit if is_first else TG_MAX_MESSAGE_LENGTH
        prefix = header if is_first else ""

        if len(remaining) <= limit:
            messages.append(prefix + remaining)
            break

        cut = _find_split_point(remaining, limit)
        messages.append(prefix + remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
        is_first = False

    return messages


class TelegramExporter(BaseExporter):
    name = "telegram"

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_ids)

    async def export(self, report: str) -> None:
        if not self.is_configured():
            return

        messages = _format_messages(report)
        base = TG_API.format(token=settings.telegram_bot_token)

        async with httpx.AsyncClient(timeout=15) as client:
            for chat_id in settings.telegram_chat_ids:
                for text in messages:
                    await self._send(client, base, chat_id, text)

    async def _send(
        self,
        client: httpx.AsyncClient,
        base: str,
        chat_id: str,
        text: str,
    ) -> None:
        try:
            resp = await client.post(
                f"{base}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("telegram_send_error", chat_id=chat_id, error=str(e))
