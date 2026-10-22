#!/usr/bin/env python3.9
"""ar_bridge.py — AgentRouter /v1/responses -> 9router-compatible /v1/chat/completions bridge.

AgentRouter quirks (verified 2026-10-22):
- Client fingerprinting: User-Agent must look like a whitelisted agent
  (hermes-agent/*, opencode/*, codex_cli_rs/*, ...). Default UA = 401
  "unauthorized client detected".
- Models only available via /v1/responses (OpenAI Responses API), NOT
  /v1/chat/completions.
- 3 models: gpt-5.6-sol, gpt-6-astra, gpt-6.1-sol

Bridge: FastAPI-less (stdlib http.server) so no new deps.
  Listens 127.0.0.1:20132
  POST /v1/chat/completions  -> translates to /v1/responses, maps back
  GET  /v1/models            -> proxies upstream /v1/models

Run:  nohup python3.9 ar_bridge.py > /tmp/ar_bridge.log 2>&1 &
"""
import json
import os
import sys
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "https://agentrouter.org"
API_KEY = os.environ.get("AR_API_KEY", "sk-***REDACTED-isi-sendiri***")
UA = "hermes-agent/4080"
PORT = 20132

MODELS = ["gpt-6.1-sol", "gpt-6-astra", "gpt-5.6-sol"]


def _upstream(method: str, path: str, body=None):
    req = urllib.request.Request(
        UPSTREAM + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 502, json.dumps({"error": {"message": f"bridge: {e}"}})


def responses_to_completions(status: int, raw: str):
    """Map OpenAI Responses API result back to chat/completions shape."""
    if status != 200:
        return status, raw
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return 200, raw
    # Extract text from output[] messages
    parts = []
    for item in d.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    parts.append(c.get("text", ""))
    text = "".join(parts)
    usage = d.get("usage") or {}
    out = {
        "id": d.get("id", "resp_bridge"),
        "object": "chat.completion",
        "created": 0,
        "model": d.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop"
                if d.get("status") == "completed"
                else d.get("status", "stop"),
            }
        ],
        "usage": usage
        or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
    return 200, json.dumps(out)


def completions_to_responses(body: dict) -> dict:
    """Translate chat/completions body into Responses API body."""
    msgs = body.get("messages", [])
    system = ""
    user_parts = []
    for m in msgs:
        role, content = m.get("role"), m.get("content")
        if role == "system":
            system = (system + "\n" + content) if system else content
        else:
            user_parts.append(content if isinstance(content, str) else json.dumps(content))
    text = user_parts[-1] if user_parts else ""
    if system:
        # Responses API supports instructions
        pass
    out = {"model": body.get("model"), "input": text}
    if system:
        out["instructions"] = system
    if body.get("max_tokens"):
        out["max_output_tokens"] = max(int(body["max_tokens"]) * 4, 256)
    # AgentRouter rejects temperature/top_p on these models (verified 400)
    # -> deliberately dropped instead of forwarded.
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep log minimal
        print(fmt % args, file=sys.stderr, flush=True)

    def _send(self, code: int, body: str, ctype="application/json"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            st, raw = _upstream("GET", "/v1/models", None)
            self._send(st, raw)
        elif self.path.startswith("/health"):
            self._send(200, json.dumps({"ok": True, "upstream": UPSTREAM}))
        else:
            self._send(404, json.dumps({"error": {"message": "not found"}}))

    def do_POST(self):
        if self.path.startswith("/v1/chat/completions"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
            rb = completions_to_responses(body)
            st, raw = _upstream("POST", "/v1/responses", rb)
            st2, raw2 = responses_to_completions(st, raw)
            self._send(st2, raw2)
        elif self.path.startswith("/v1/responses"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
            st, raw = _upstream("POST", "/v1/responses", body)
            self._send(st, raw)
        else:
            self._send(404, json.dumps({"error": {"message": "not found"}}))


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ar_bridge on 127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
