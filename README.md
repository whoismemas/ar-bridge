<div align="center">

# 🐀 ar_bridge

**AgentRouter `/v1/responses` → OpenAI-compatible `/v1/chat/completions` bridge**

Zero deps · Python 3.9+ stdlib only · single file

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)

</div>

---

## Why this exists

AgentRouter (agentrouter.org) quirks, verified 2026-10-22:

| Quirk | Without bridge | With bridge |
|-------|---------------|-------------|
| **Client fingerprinting** — `User-Agent` must look like a whitelisted agent | default UA → `401 unauthorized client` | sends `hermes-agent/4080` |
| **Responses API only** | `/v1/chat/completions` → 404 | transparent translation |
| **No temperature** — `temperature`/`top_p` rejected | 400 `Unsupported parameter` | dropped silently |
| **Reasoning eats max_tokens** | `max_tokens: 16` → empty text | scaled `max_output_tokens = max(max_tokens*4, 256)` |

Models: `gpt-6.1-sol` · `gpt-6-astra` · `gpt-5.6-sol`

## Quick start

```bash
export AR_API_KEY="sk-your-agentrouter-key"
python3.9 ar_bridge.py &
# bridge on 127.0.0.1:20132
```

## Watchdog (optional but recommended)

```bash
chmod +x ar_bridge_watchdog.sh
( crontab -l 2>/dev/null; echo "* * * * * $PWD/ar_bridge_watchdog.sh" ) | crontab -
```

## API

| Route | Behavior |
|-------|----------|
| `POST /v1/chat/completions` | Translate → `/v1/responses`, map back. Sanitizes params. |
| `POST /v1/responses` | Passthrough to upstream |
| `GET /v1/models` | Proxied from upstream |
| `GET /health` | `{"ok": true, ...}` |

## Test

```bash
curl -s http://127.0.0.1:20132/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-6.1-sol","messages":[{"role":"user","content":"hi"}],"max_tokens":32,"stream":false}'
```

## 9router integration (optional)

Register as custom provider node → point at `http://127.0.0.1:20132/v1` → models appear as `ar/gpt-6.1-sol` etc.

## License

MIT
