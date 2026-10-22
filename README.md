# ar_bridge

AgentRouter `/v1/responses` → OpenAI-compatible `/v1/chat/completions` bridge. Stdlib-only (Python 3.9+, zero deps).

## Why this exists

AgentRouter (agentrouter.org) quirks, verified 2026-10-22:

- **Client fingerprinting**: `User-Agent` must look like a whitelisted agent (`hermes-agent/*`, `opencode/*`, `codex_cli_rs/*`). Default UA → 401.
- **Responses API only**: models are served via `/v1/responses`, NOT `/v1/chat/completions`.
- **No temperature**: requests carrying `temperature`/`top_p` → 400 `Unsupported parameter`.
- **Reasoning eats max_tokens**: small `max_tokens` (e.g. 16) gets consumed by reasoning → empty text.

This bridge fixes all four transparently.

## Files

| File | Purpose |
|------|---------|
| `ar_bridge.py` | The bridge — listens on `127.0.0.1:20132` |
| `ar_bridge_watchdog.sh` | Cron watchdog, restarts bridge if dead |

## Setup

```bash
# 1. Set your key (line 27) or export:
export AR_API_KEY="sk-..."
# then edit ar_bridge.py: API_KEY = os.environ.get("AR_API_KEY", "")

# 2. Run
nohup python3.9 ar_bridge.py > /tmp/ar_bridge.log 2>&1 &

# 3. Watchdog (every minute via cron)
chmod +x ar_bridge_watchdog.sh
( crontab -l 2>/dev/null; echo "* * * * * $PWD/ar_bridge_watchdog.sh" ) | crontab -
```

## API

| Route | Behavior |
|-------|----------|
| `POST /v1/chat/completions` | Translates → `/v1/responses`, maps back. Drops `temperature`/`top_p`. Scales `max_output_tokens = max(max_tokens*4, 256)`. |
| `POST /v1/responses` | Passthrough to upstream |
| `GET /v1/models` | Proxied from upstream |
| `GET /health` | `{"ok": true, "upstream": "..."}` |

Models: `gpt-6.1-sol`, `gpt-6-astra`, `gpt-5.6-sol`

## Test

```bash
curl -s http://127.0.0.1:20132/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-6.1-sol","messages":[{"role":"user","content":"hi"}],"max_tokens":32,"stream":false}'
```

## 9router integration (optional)

Register as custom provider node → point at `http://127.0.0.1:20132/v1` → models appear as `ar/gpt-6.1-sol` etc.
