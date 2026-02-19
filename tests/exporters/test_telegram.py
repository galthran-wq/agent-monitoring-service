import respx
from httpx import Response

from src.exporters.telegram import TG_MAX_MESSAGE_LENGTH, TelegramExporter, _format_messages, _md_to_html


def test_md_to_html_bold():
    assert _md_to_html("**hello**") == "<b>hello</b>"
    assert _md_to_html("__hello__") == "<b>hello</b>"


def test_md_to_html_italic():
    assert _md_to_html("*hello*") == "<i>hello</i>"


def test_md_to_html_code():
    assert _md_to_html("`code`") == "<code>code</code>"


def test_md_to_html_mixed():
    text = "**Overall Status**: 🟢 Healthy\n**Errors**: `none`"
    result = _md_to_html(text)
    assert "<b>Overall Status</b>" in result
    assert "<b>Errors</b>" in result
    assert "<code>none</code>" in result


def test_format_messages_converts_markdown():
    msgs = _format_messages("**Service Health**: all ok")
    assert len(msgs) == 1
    assert "<b>Service Health</b>" in msgs[0]
    assert "**" not in msgs[0]


def test_format_messages_splits_long_report():
    report = "x" * 10000
    msgs = _format_messages(report)
    assert len(msgs) >= 2
    for msg in msgs:
        assert len(msg) <= TG_MAX_MESSAGE_LENGTH
    assert "truncated" not in "".join(msgs)


def test_format_messages_preserves_full_content():
    report = "word " * 2000  # ~10000 chars
    msgs = _format_messages(report)
    joined = "".join(msg.split("\n\n", 1)[-1] if i == 0 else msg for i, msg in enumerate(msgs))
    # All original words should be present (whitespace may differ at split boundaries)
    assert joined.replace(" ", "").replace("\n", "") == report.replace(" ", "")


def test_format_messages_includes_header():
    msgs = _format_messages("All systems healthy")
    assert len(msgs) == 1
    assert "Agent Monitoring Report" in msgs[0]
    assert "All systems healthy" in msgs[0]


def test_format_messages_header_only_on_first():
    report = "x" * 10000
    msgs = _format_messages(report)
    assert "Agent Monitoring Report" in msgs[0]
    for msg in msgs[1:]:
        assert "Agent Monitoring Report" not in msg


async def test_telegram_export_sends_message(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("Test report")

    assert exporter._message_ids.get("123") == [42]


async def test_telegram_export_sends_multiple_messages_for_long_report(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()
    call_count = 0

    with respx.mock:
        route = respx.post("https://api.telegram.org/bottest-token/sendMessage")

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            return Response(200, json={"ok": True, "result": {"message_id": 40 + call_count}})

        route.mock(side_effect=side_effect)

        await exporter.export("x" * 10000)

    assert len(exporter._message_ids["123"]) >= 2
    assert call_count >= 2


async def test_telegram_export_edits_existing_message(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()
    exporter._message_ids["123"] = [42]

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/editMessageText").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("Updated report")

    assert exporter._message_ids["123"] == [42]


async def test_telegram_export_falls_back_to_send_on_edit_failure(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()
    exporter._message_ids["123"] = [42]

    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/editMessageText").mock(
            return_value=Response(400, json={"ok": False, "description": "Bad Request: message not found"})
        )
        respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 99}})
        )

        await exporter.export("Fallback report")

    assert exporter._message_ids["123"] == [99]


async def test_telegram_not_configured(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", [])

    exporter = TelegramExporter()
    assert exporter.is_configured() is False
    # Should be a no-op
    await exporter.export("test")
