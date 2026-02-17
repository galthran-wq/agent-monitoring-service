from datetime import UTC, datetime

import httpx
import structlog

from src.config import settings
from src.exporters.base import BaseExporter

logger = structlog.get_logger()

TG_API = "https://api.telegram.org/bot{token}"
TG_MAX_MESSAGE_LENGTH = 4096


def _format_message(report: str) -> str:
    ts = datetime.now(UTC).strftime("%H:%M %d.%m.%Y")
    header = f"<b>Agent Monitoring Report</b> ({ts})\n\n"
    max_body = TG_MAX_MESSAGE_LENGTH - len(header) - 20
    body = report[:max_body]
    if len(report) > max_body:
        body += "\n... (truncated)"
    return header + body


class TelegramExporter(BaseExporter):
    name = "telegram"

    def __init__(self) -> None:
        self._message_ids: dict[str, int] = {}

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_ids)

    async def export(self, report: str) -> None:
        if not self.is_configured():
            return

        text = _format_message(report)
        base = TG_API.format(token=settings.telegram_bot_token)

        async with httpx.AsyncClient(timeout=15) as client:
            for chat_id in settings.telegram_chat_ids:
                await self._export_to_chat(client, base, chat_id, text)

    async def _export_to_chat(self, client: httpx.AsyncClient, base: str, chat_id: str, text: str) -> None:
        message_id = self._message_ids.get(chat_id)

        if message_id:
            try:
                resp = await client.post(
                    f"{base}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                )
                data: dict = {}
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                if resp.status_code == 200 and data.get("ok"):
                    return
                description = data.get("description")
                if isinstance(description, str) and "message is not modified" in description.lower():
                    return
            except Exception as e:
                logger.warning("telegram_edit_error", chat_id=chat_id, error=str(e))

        try:
            resp = await client.post(
                f"{base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                self._message_ids[chat_id] = data["result"]["message_id"]
        except Exception as e:
            logger.warning("telegram_send_error", chat_id=chat_id, error=str(e))
