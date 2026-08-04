"""OpenAI-compatible proxy: POST /v1/chat/completions.

Point any agent here with a BASE_URL change. Non-streaming (by design, see plan).
Arm selection via X-Headroom-Arm header (adaptive|stock|compact|off), session via
X-Headroom-Session. Also serves the dashboard and its data API.
"""

import os
import time
import hashlib

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from . import controller, log, upstream

WINDOW = int(os.environ.get("HEADROOM_WINDOW", "32000"))
DASH = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "index.html")

app = FastAPI(title="Headroom")
_sessions: dict[str, controller.Session] = {}


def get_session(sid: str, arm: str) -> controller.Session:
    key = f"{sid}:{arm}"
    if key not in _sessions:
        _sessions[key] = controller.Session(id=sid, arm=arm, window=WINDOW)
    return _sessions[key]


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    messages = body.get("messages", [])
    arm = req.headers.get("X-Headroom-Arm", "adaptive")
    sid = req.headers.get("X-Headroom-Session") or hashlib.sha256(
        (messages[0].get("content", "") if messages else "").encode()
    ).hexdigest()[:12]

    query = next((m.get("content", "") for m in reversed(messages)
                  if m.get("role") == "user"), "")[:400]

    if arm == "off":
        outgoing = messages
    else:
        sess = get_session(sid, arm)
        outgoing = controller.handle(sess, messages, query)

    t0 = time.time()
    resp = upstream.chat(outgoing, body.get("model"),
                         body.get("max_tokens") or 512)
    usage = resp.get("usage", {})
    log.write({"kind": "upstream", "session": sid, "arm": arm,
               "latency_ms": round(1000 * (time.time() - t0)),
               "upstream": upstream.name(), "model": resp.get("model"),
               "provider_prompt_tokens": usage.get("prompt_tokens"),
               "provider_cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens")})
    return JSONResponse(resp)


@app.get("/api/log")
def api_log(session: str = None, arm: str = None, kind: str = None, turn: int = None):
    rows = log.read_all()
    if session:
        rows = [r for r in rows if r.get("session") == session]
    if arm:
        rows = [r for r in rows if r.get("arm") == arm]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    if turn is not None:
        rows = [r for r in rows if r.get("turn") == turn]
    return rows


@app.get("/api/summary")
def api_summary():
    import json
    path = "logs/benchmark_summary.json"
    if os.path.exists(path):
        return json.load(open(path))
    return JSONResponse({"error": "no benchmark run yet"}, status_code=404)


@app.get("/api/segment/{sid}")
def api_segment(sid: str):
    for sess in _sessions.values():
        seg = sess.store.by_id.get(sid)
        if seg:
            return {"id": sid, "class": seg.cls, "priority": seg.priority,
                    "arrival_turn": seg.arrival_turn, "original": seg.original,
                    "reps": {lvl: {"text": t, "tokens": n, "backend": b}
                             for lvl, (t, n, b) in seg.reps.items()}}
    # benchmark runs persist segments to disk; the dashboard API can read those too
    import json
    path = os.environ.get("HEADROOM_SEGMENTS", "logs/segments.json")
    if os.path.exists(path):
        data = json.load(open(path))
        if sid in data:
            return data[sid]
    return JSONResponse({"error": "unknown segment"}, status_code=404)


@app.get("/")
def dashboard():
    return FileResponse(DASH)


@app.get("/health")
def health():
    return {"ok": True, "upstream": upstream.name(), "window": WINDOW}
