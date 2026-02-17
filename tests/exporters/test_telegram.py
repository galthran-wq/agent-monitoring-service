import respx
from httpx import Response
from src.exporters.telegram import TelegramExporter, _format_message


def test_format_message_truncates_long_report():
    report = "x" * 10000
    msg = _format_message(report)
    assert len(msg) <= 4096
    assert "truncated" in msg


def test_format_message_includes_header():
    msg = _format_message("All systems healthy")
    assert "Agent Monitoring Report" in msg
    assert "All systems healthy" in msg


async def test_telegram_export_sends_message(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("Test report")

    assert exporter._message_ids.get("123") == 42


async def test_telegram_export_edits_existing_message(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()
    exporter._message_ids["123"] = 42

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/editMessageText").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("Updated report")


async def test_telegram_export_falls_back_to_send_on_edit_failure(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()
    exporter._message_ids["123"] = 42

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/editMessageText").mock(
            return_value=Response(400, json={"ok": False, "description": "Bad Request: message not found"})
        )
        respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 99}})
        )

        await exporter.export("Fallback report")

    assert exporter._message_ids["123"] == 99


async def test_telegram_not_configured(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", [])

    exporter = TelegramExporter()
    assert exporter.is_configured() is False
    # Should be a no-op
    await exporter.export("test")
