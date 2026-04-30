# Meridian Electronics — AI Customer Support Chatbot

A production-leaning prototype of an AI support agent for Meridian Electronics. Connects to a backend MCP server, dynamically discovers business tools, and serves customers end-to-end: browse products, authenticate with email + PIN, look up order history, and place new orders.

Built as a 3-hour assessment. Not feature-complete — but architected so the engineering team can security-review and ship it without a rewrite.

---

## What it does

Aria, the assistant, handles four flows:

1. **Browse** — search and filter the product catalog by category, name, or SKU. Live stock and prices.
2. **Authenticate** — verifies a returning customer via email + 4-digit PIN before any account-scoped action.
3. **Order history** — once verified, the customer can ask about past orders and order detail.
4. **Place orders** — confirms SKU/price/stock, reads the order back, and only commits on explicit user confirmation.

It refuses anything off-topic, defends against prompt injection, and never echoes the customer's PIN.

---

## Architecture

```
┌──────────────┐    HTTP     ┌────────────────┐    JSON-RPC / SSE    ┌──────────────┐
│  Gradio UI   │ ──────────▶ │  SupportAgent  │ ───────────────────▶ │  MCP server  │
│  (src/ui.py) │             │  (src/agent.py)│                      │  (Cloud Run) │
└──────────────┘             └────────────────┘                      └──────────────┘
       │                            │
       │                            ▼
       │                     ┌────────────────┐
       │                     │   OpenAI API   │
       │                     │  (gpt-4o-mini) │
       │                     └────────────────┘
       │
       └─── per-session conversation history (kept client-side via gr.State)
```

**Layers, intentionally separable:**

| Module | Responsibility |
| --- | --- |
| `src/config.py` | Strict env-driven settings, fail-fast on missing keys. |
| `src/mcp_client.py` | Async MCP client over Streamable HTTP. Discovers tools and invokes them. Server-stateless (fresh session per call) so Cloud Run idle restarts are tolerated. |
| `src/agent.py` | LLM tool-calling loop. Stateless across instances — caller owns history. Capped iterations to prevent runaway loops. |
| `src/prompts.py` | Versioned system prompt (`PROMPT_VERSION`). Single source of truth for behavior. |
| `src/security.py` | Input length cap, injection-pattern detection, untrusted-input wrapping. |
| `src/observability.py` | JSON structured logging with PIN redaction, per-turn token + latency metrics. |
| `src/ui.py` | Gradio chat UI; owns session state and surface-level UX. |

The agent has **zero hard-coded tool calls**. It discovers MCP tools at startup, translates their JSON schemas into OpenAI function specs, and lets the model choose. Add a tool to the MCP server → it shows up here automatically.

---

## Key decisions and tradeoffs

| Decision | Why |
| --- | --- |
| **GPT-4o-mini** as default model | Cheap (~$0.15 / 1M input tokens), strong tool-calling, low latency. Per-conversation cost stays well under a cent. |
| **No DB on our side** for session state | Conversation history lives in `gr.State` for the demo. For production we'd swap in Redis or Postgres — but adding it now would be premature. The agent is already stateless to make that swap trivial. |
| **Auth state lives in conversation history**, not a separate session store | The system prompt enforces "only use a `customer_id` you got from `verify_customer_pin` in *this* conversation". Simpler, auditable in traces, and correctly scoped per chat session. |
| **Fresh MCP session per tool call** | Avoids holding long-lived sessions across user idles; survives Cloud Run cold restarts. |
| **JSON logs, not just print** | Production telemetry should be ingestible. PINs are regex-redacted before logs leave the process. |
| **Tests run with mocked OpenAI + live MCP probes** | Live MCP tests catch contract drift; mocked agent tests run instantly with zero API spend. |
| **Gradio over Streamlit / Chainlit** | Native HF Spaces support, async-friendly, and `gr.State` made session-scoped history cleanly explicit. |

---

## Setup

```bash
# 1. clone and enter
git clone <this repo>
cd andela-mcp-challenge

# 2. virtualenv
python -m venv .venv
.venv/Scripts/activate     # Windows
source .venv/bin/activate  # macOS / Linux

# 3. deps
pip install -r requirements.txt

# 4. config
cp .env.example .env
# edit .env and set OPENAI_API_KEY

# 5. run
python app.py
# open http://localhost:7860
```

Required env vars:

| Var | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | *(required)* | OpenAI API key. |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model name. |
| `MCP_SERVER_URL` | Meridian's hosted server | Override for local MCP servers. |
| `LOG_LEVEL` | `INFO` | Standard Python log levels. |

---

## Tests

```bash
pytest                         # full suite (live MCP + mocked agent)
SKIP_LIVE_MCP=1 pytest         # offline / CI: skips live MCP integration
```

The suite covers:

- **Unit** — input validation, injection-pattern detection, PIN redaction, token accounting.
- **Agent** — tool-calling loop happy path, multi-iteration loops, iteration cap, injection annotation, empty-input rejection. All with mocked OpenAI + MCP.
- **Live integration** — real round-trip against the MCP server: tool discovery, valid PIN, wrong PIN, search, unknown SKU.

---

## Test customers (assessment data)

| Email | PIN |
| --- | --- |
| donaldgarcia@example.net | 7912 |
| michellejames@example.com | 1520 |
| laurahenderson@example.org | 1488 |
| spenceamanda@example.org | 2535 |
| glee@example.net | 4582 |
| williamsthomas@example.net | 4811 |
| justin78@example.net | 9279 |
| jason31@example.com | 1434 |
| samuel81@example.com | 4257 |
| williamleon@example.net | 9928 |

These are test fixtures only; in production no PINs would ship in a README.

---

## Security posture

- **System prompt guardrails** — verification required for any account-scoped tool call; off-topic redirected; PIN never echoed.
- **Input wrapping** — known injection phrases (`ignore previous instructions`, `developer mode`, etc.) are wrapped in `<untrusted_user_input>` tags so the model treats them as data, not commands.
- **Length cap** on user messages.
- **Log redaction** — any field that looks like a PIN is masked before logs are emitted.
- **Iteration cap** — the agent won't loop forever on a stuck tool.
- **No secrets in code** — everything via env. `.env` is gitignored.

---

## Known limitations and what I'd ship next

| Limitation | Next step |
| --- | --- |
| No persistent session store. | Move history + verified-customer state into Redis with short TTL. |
| No streaming token output to the UI. | Switch to OpenAI's streaming API and Gradio's incremental yields. |
| Observability is local-only (JSON to stdout). | Wire Langfuse / LangSmith for trace export, p95 latency, and cost rollups per session. |
| One-shot order confirmation only. | Add cart-style multi-item order building before commit. |
| No rate limiting per user / IP. | Add a simple token bucket in front of the chat endpoint. |
| English only. | i18n via system-prompt locale variants. |
| Shared OpenAI key. | Per-tenant key rotation + spend caps. |

---

## Repo layout

```
andela-mcp-challenge/
├── app.py                 # entrypoint
├── requirements.txt
├── pyproject.toml
├── .env.example
├── src/
│   ├── config.py
│   ├── mcp_client.py
│   ├── agent.py
│   ├── prompts.py
│   ├── security.py
│   ├── observability.py
│   └── ui.py
└── tests/
    ├── conftest.py
    ├── test_security.py
    ├── test_observability.py
    ├── test_agent.py
    └── test_mcp_client.py
```
