import respx
from httpx import Response
from src.exporters.telegram import TG_MAX_MESSAGE_LENGTH, TelegramExporter, _format_messages


def test_format_messages_passes_html_through():
    msgs = _format_messages("<b>Service Health</b>: all ok")
    assert len(msgs) == 1
    assert "<b>Service Health</b>" in msgs[0]


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
        route = respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("Test report")

    assert route.call_count == 1


async def test_telegram_export_sends_new_messages_each_time(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "test-token")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", ["123"])

    exporter = TelegramExporter()

    with respx.mock:
        route = respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        await exporter.export("First report")
        await exporter.export("Second report")

    assert route.call_count == 2


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

    assert call_count >= 2


async def test_telegram_not_configured(monkeypatch):
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_bot_token", "")
    monkeypatch.setattr("src.exporters.telegram.settings.telegram_chat_ids", [])

    exporter = TelegramExporter()
    assert exporter.is_configured() is False
    # Should be a no-op
    await exporter.export("test")
