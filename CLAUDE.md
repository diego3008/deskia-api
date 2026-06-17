# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Uses `uv` for dependency management and `uvicorn` as the ASGI server.

```bash
# Install dependencies
uv sync

# Run the server (development)
uv run uvicorn main:app --reload

# Run the server (production-style)
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Add a dependency
uv add <package>
```

There are no tests yet. The `.env` file (not committed) must define `BOT_TOKEN`, `WEBHOOK_URL`, `AGENT_SERVICE_URL`, `LANGGRAPH_ASSISTANT_ID`, and `LAGGRAPH_API_KEY`.

## Architecture

This is a **Telegram webhook gateway** — a thin FastAPI service that bridges Telegram and a LangGraph agent service.

**Request flow:**
1. Telegram POSTs an update to `POST /webhook/telegram`
2. `src/api/telegram.py` deserializes it via `python-telegram-bot`, normalizes it into an `IncomingMessage` (platform-agnostic schema in `src/schemas.py`)
3. `src/api/agent_client.py` forwards the normalized message to the LangGraph agent at `AGENT_SERVICE_URL/runs/wait`
4. The last `ai`-typed message in the agent's response is extracted and sent back to the user via the bot

**Key design decisions:**
- PTB (`python-telegram-bot`) runs in webhook mode (`updater=None`) — Telegram pushes updates rather than PTB polling. The `Application` is initialized in the FastAPI `lifespan` and stored on `app.state.ptb`.
- The webhook endpoint always returns HTTP 200, even on errors — Telegram retries on any other status, which would cause duplicate processing.
- `IncomingMessage` is intentionally platform-agnostic so the agent service never deals with raw Telegram objects.

**Module layout:**
- `main.py` — FastAPI app, lifespan (PTB init + webhook registration), health endpoint
- `src/config.py` — Pydantic `Settings` loaded from `.env`
- `src/schemas.py` — `IncomingMessage` and `AgentResponse` models
- `src/api/telegram.py` — webhook route handler
- `src/api/agent_client.py` — HTTP client that calls the LangGraph agent
