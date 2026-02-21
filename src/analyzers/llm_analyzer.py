from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from openai import AsyncOpenAI

from src.config import settings

if TYPE_CHECKING:
    from src.sources.base import SourceData

logger = structlog.get_logger()

SYSTEM_PROMPT = """\
You are an infrastructure monitoring analyst. Analyze the provided logs and metrics data \
and produce a concise status report.

IMPORTANT: Format your output using Telegram HTML tags ONLY. \
Do NOT use Markdown syntax (no **, __, `, ```, #). \
Allowed tags: <b>bold</b>, <i>italic</i>, <code>inline code</code>, <pre>code block</pre>.

Structure your report EXACTLY as follows:

<b>Overall Status</b>: 🟢 Healthy / 🟡 Degraded / 🔴 Critical

<b>Service Health</b>:
- List each service and its status

<b>Errors</b>:
- Summarize error patterns, group similar errors

<b>Performance</b>:
- Latency, request rates, any anomalies

<b>Warnings</b>:
- Notable warnings that may need attention

<b>Recommendations</b>:
- Actionable items, if any

Be concise. Focus on actionable insights. Skip sections with no relevant data.\
"""


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _truncate_to_budget(source_data: list[SourceData], max_tokens: int) -> str:
    sections: list[str] = []
    for sd in source_data:
        sections.append(f"=== {sd.source_name.upper()} ===\nSummary: {sd.summary}\n\n{sd.raw_text}")

    combined = "\n\n".join(sections)

    if _estimate_tokens(combined) <= max_tokens:
        return combined

    # Progressive truncation: halve raw_text per source until it fits
    for divisor in (2, 4, 8, 16):
        sections = []
        for sd in source_data:
            limit = max(200, len(sd.raw_text) // divisor)
            truncated_raw = sd.raw_text[:limit] + "\n... (truncated)"
            sections.append(f"=== {sd.source_name.upper()} ===\nSummary: {sd.summary}\n\n{truncated_raw}")
        combined = "\n\n".join(sections)
        if _estimate_tokens(combined) <= max_tokens:
            return combined

    # Hard character cutoff
    max_chars = max_tokens * 4
    return combined[:max_chars] + "\n... (hard truncated)"


def _build_fallback_report(source_data: list[SourceData]) -> str:
    lines = ["<b>Overall Status</b>: ⚠️ LLM unavailable — fallback summary", ""]
    for sd in source_data:
        lines.append(f"<b>{sd.source_name}</b>: {sd.summary}")
    return "\n".join(lines)


def _build_client() -> AsyncOpenAI:
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=60.0,
    )

    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
        try:
            from langsmith.wrappers import wrap_openai

            client = wrap_openai(client)
            logger.info("langsmith_tracing_enabled")
        except ImportError:
            logger.warning("langsmith_package_not_installed")

    return client


async def analyze(source_data: list[SourceData]) -> str:
    if not settings.llm_api_key:
        logger.info("llm_api_key_not_set", msg="Using fallback summary")
        return _build_fallback_report(source_data)

    user_content = _truncate_to_budget(source_data, settings.llm_max_input_tokens)

    try:
        client = _build_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_output_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        content = response.choices[0].message.content or ""
        return content
    except Exception as e:
        logger.error("llm_analysis_error", error=str(e))
        return _build_fallback_report(source_data)
