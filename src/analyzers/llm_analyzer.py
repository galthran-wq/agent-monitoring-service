import httpx
import structlog

from src.config import settings
from src.sources.base import SourceData

logger = structlog.get_logger()

SYSTEM_PROMPT = """\
You are an infrastructure monitoring analyst. Analyze the provided logs and metrics data \
and produce a concise status report.

Structure your report EXACTLY as follows:

**Overall Status**: 🟢 Healthy / 🟡 Degraded / 🔴 Critical

**Service Health**:
- List each service and its status

**Errors**:
- Summarize error patterns, group similar errors

**Performance**:
- Latency, request rates, any anomalies

**Warnings**:
- Notable warnings that may need attention

**Recommendations**:
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
    lines = ["**Overall Status**: ⚠️ LLM unavailable — fallback summary", ""]
    for sd in source_data:
        lines.append(f"**{sd.source_name}**: {sd.summary}")
    return "\n".join(lines)


async def analyze(source_data: list[SourceData]) -> str:
    if not settings.llm_api_key:
        logger.info("llm_api_key_not_set", msg="Using fallback summary")
        return _build_fallback_report(source_data)

    user_content = _truncate_to_budget(source_data, settings.llm_max_input_tokens)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "max_tokens": settings.llm_max_output_tokens,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("llm_analysis_error", error=str(e))
        return _build_fallback_report(source_data)
