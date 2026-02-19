import html
import re
from datetime import UTC, datetime

import httpx
import structlog

from src.config import settings
from src.exporters.base import BaseExporter

logger = structlog.get_logger()

TG_API = "https://api.telegram.org/bot{token}"
TG_MAX_MESSAGE_LENGTH = 4096


def _md_to_html(text: str) -> str:
    """Convert basic Markdown formatting to Telegram HTML after html.escape()."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _find_split_point(text: str, max_length: int) -> int:
    """Find a safe point to split text at or before max_length."""
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
    body = _md_to_html(html.escape(report, quote=False))

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

    def __init__(self) -> None:
        self._message_ids: dict[str, list[int]] = {}

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_ids)

    async def export(self, report: str) -> None:
        if not self.is_configured():
            return

        messages = _format_messages(report)
        base = TG_API.format(token=settings.telegram_bot_token)

        async with httpx.AsyncClient(timeout=15) as client:
            for chat_id in settings.telegram_chat_ids:
                await self._export_to_chat(client, base, chat_id, messages)

    async def _export_to_chat(
        self, client: httpx.AsyncClient, base: str, chat_id: str, messages: list[str]
    ) -> None:
        old_ids = self._message_ids.get(chat_id, [])
        new_ids: list[int] = []

        for i, text in enumerate(messages):
            existing_id = old_ids[i] if i < len(old_ids) else None
            sent_id = await self._send_or_edit(client, base, chat_id, text, existing_id)
            if sent_id is not None:
                new_ids.append(sent_id)

        if new_ids:
            self._message_ids[chat_id] = new_ids

    async def _send_or_edit(
        self,
        client: httpx.AsyncClient,
        base: str,
        chat_id: str,
        text: str,
        message_id: int | None,
    ) -> int | None:
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
                data: dict[str, object] = {}
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                if resp.status_code == 200 and data.get("ok"):
                    return message_id
                description = data.get("description")
                if isinstance(description, str) and "message is not modified" in description.lower():
                    return message_id
            except Exception as e:
                logger.warning("telegram_edit_error", chat_id=chat_id, error=str(e))

        try:
            resp = await client.post(
                f"{base}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
            send_data: dict[str, object] = resp.json()
            if send_data.get("ok"):
                result = send_data["result"]
                assert isinstance(result, dict)
                msg_id = result["message_id"]
                assert isinstance(msg_id, int)
                return msg_id
        except Exception as e:
            logger.warning("telegram_send_error", chat_id=chat_id, error=str(e))

        return None
