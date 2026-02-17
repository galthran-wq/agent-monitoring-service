# Agent Monitoring Service

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type_checker-mypy-blue)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Automated infrastructure monitoring service. Periodically pulls logs from Loki and metrics from Prometheus, analyzes them via a cheap LLM (Gemini Flash via OpenRouter), and pushes concise HTML summaries to Telegram.

## How It Works

```
LokiSource ──┐
              ├──> AgentMonitor.tick() ──> LLM Analyzer ──> TelegramExporter
PrometheusSource──┘
```

Every N seconds (default 1 hour):
1. **Sources** fetch data in parallel — Loki errors/warnings, Prometheus health/rates/latency
2. **LLM Analyzer** truncates data to token budget, sends to a cheap LLM, gets a structured summary
3. **Exporters** push the summary to Telegram (edits previous message to avoid spam)
4. If LLM is unavailable, a basic statistical fallback summary is generated instead

## Quick Start

```bash
make install
make run
```

## Configuration

All env vars use the `AGENT_MONITORING_` prefix.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_MONITORING_MONITOR_INTERVAL` | `3600` | Seconds between reports |
| `AGENT_MONITORING_LOOKBACK_PERIOD` | `3600` | How far back to query |
| `AGENT_MONITORING_LLM_API_KEY` | `""` | API key for LLM provider |
| `AGENT_MONITORING_LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint |
| `AGENT_MONITORING_LLM_MODEL` | `google/gemini-2.0-flash` | Model to use |
| `AGENT_MONITORING_LLM_MAX_INPUT_TOKENS` | `12000` | Token budget for source data |
| `AGENT_MONITORING_LLM_MAX_OUTPUT_TOKENS` | `2000` | Max response length |
| `AGENT_MONITORING_LOKI_URL` | `http://loki:3100` | Loki endpoint |
| `AGENT_MONITORING_LOKI_ENABLED` | `true` | Enable/disable Loki source |
| `AGENT_MONITORING_LOKI_EXTRA_QUERIES` | `""` | Comma-separated extra LogQL queries |
| `AGENT_MONITORING_PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus endpoint |
| `AGENT_MONITORING_PROMETHEUS_ENABLED` | `true` | Enable/disable Prometheus source |
| `AGENT_MONITORING_PROMETHEUS_EXTRA_QUERIES` | `""` | Comma-separated extra PromQL queries |
| `AGENT_MONITORING_TELEGRAM_BOT_TOKEN` | `""` | Telegram bot token |
| `AGENT_MONITORING_TELEGRAM_CHAT_IDS` | `""` | Comma-separated chat IDs |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |
| GET | `/report` | Last generated monitoring report |

## Commands

| Command | Description |
|---|---|
| `make install` | Install dependencies |
| `make run` | Run dev server with hot reload |
| `make test` | Run tests with coverage |
| `make lint` | Run ruff + mypy |
| `make format` | Auto-format code |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run Docker container |

## Project Structure

```
src/
├── main.py           — app factory, lifespan background task for monitor
├── config.py         — pydantic-settings with AGENT_MONITORING_ prefix
├── dependencies.py   — FastAPI dependency injection (MonitorDep)
├── api/
│   ├── router.py     — aggregated API router
│   └── endpoints/    — health + report handlers
├── sources/          — data source plugins
│   ├── base.py       — BaseSource ABC
│   ├── loki.py       — Loki HTTP API queries
│   └── prometheus.py — Prometheus HTTP API queries
├── analyzers/
│   └── llm_analyzer.py — token budget, LLM call, fallback summary
├── exporters/        — output plugins
│   ├── base.py       — BaseExporter ABC
│   └── telegram.py   — edit-previous-message pattern
├── services/
│   └── monitor.py    — AgentMonitor orchestration loop
├── schemas/          — Pydantic request/response models
└── core/
    ├── exceptions.py — custom exceptions + handlers
    └── middleware.py  — CORS, request logging, request ID
```
