"""Milestone checks from the execution plan. Run: .venv/bin/python tests/test_headroom.py

H1-3: an agent pointed at the proxy behaves as if it weren't there; every call logged.
H3-6: 40-turn synthetic run — occupancy stays under ceiling, epochs fire,
      pinned content byte-identical, recompression always from original.
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["HEADROOM_LOG"] = tempfile.mkstemp(suffix=".jsonl")[1]
# tests always run offline against the mock — never burn real credits.
# import triggers the package's .env loader, so pop keys AFTER it runs.
import headroom_proxy  # noqa: E402,F401
os.environ.pop("SLEEPY_AI_API_KEY", None)
os.environ.pop("PARITOK_API_KEY", None)

import httpx

from headroom_proxy import controller, log, tokens
from headroom_proxy.app import app


def fake_transcript(n_turns: int) -> list[dict]:
    msgs = [{"role": "system", "content": "You are a debugging agent. [PINNED] Never touch vendor/."}]
    for t in range(n_turns):
        msgs.append({"role": "user", "content": f"Turn {t}: investigate module_{t}.py please"})
        msgs.append({"role": "assistant", "content": f"Reading module_{t}.py now."})
        filler = "\n".join(f"line {i}: value_{t}_{i} = compute({i})" for i in range(60))
        msgs.append({"role": "user", "content": f"TOOL OUTPUT: pytest module_{t}\n{filler}"})
    return msgs


def test_passthrough():
    transport = httpx.ASGITransport(app=app)

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post("/v1/chat/completions",
                             headers={"X-Headroom-Arm": "off"},
                             json={"model": "gpt-4",
                                   "messages": [{"role": "user", "content": "hello"}]})
            assert r.status_code == 200
            body = r.json()
            assert body["choices"][0]["message"]["role"] == "assistant"
            assert "usage" in body and body["usage"]["prompt_tokens"] > 0
    asyncio.run(run())
    rows = log.read_all()
    assert any(r["kind"] == "upstream" for r in rows), "upstream call must be logged"
    print("PASS passthrough + logging")


def test_controller_40_turns():
    window = 8000
    sess = controller.Session(id="t40", arm="adaptive", window=window)
    system_original = None
    for t in range(1, 41):
        msgs = fake_transcript(t)
        if system_original is None:
            system_original = msgs[0]["content"]
        out = controller.handle(sess, msgs, query=f"turn {t}")
        sent = sum(tokens.count(m["content"]) for m in out)
        assert sent <= window * 1.02 or sess.dead, f"turn {t}: {sent} tokens over ceiling without dying"
        # pinned system prompt byte-identical, always
        assert out[0]["content"] == system_original, "pinned content was touched"
    assert sess.epoch >= 1, f"expected at least one epoch, got {sess.epoch}"
    assert sess.epoch < 40 / 3, f"epochs must stay rare even saturated, got {sess.epoch}"
    assert not sess.dead, "40-turn session should survive an 8k window under adaptive"
    # recompression invariant: every cached rep derives from the original
    for seg in sess.store.by_id.values():
        for lvl, (text, _, _) in seg.reps.items():
            if lvl == "L0":
                assert text == seg.original
    # stock arm compresses history hard even with an empty window
    s2 = controller.Session(id="tstock", arm="stock", window=10**9)
    out2 = controller.handle(s2, fake_transcript(10), "q")
    l3_rows = [r for r in log.read_all()
               if r.get("session") == "tstock" and r.get("assigned_level") == "L3"]
    assert l3_rows, "stock arm must L3 history regardless of occupancy"
    assert len(out2) == len(fake_transcript(10))
    print(f"PASS controller: 40 turns, {sess.epoch} epochs, occupancy held, pinned intact")


def test_survives_noop_compressor():
    """Paritok's hosted path returned identical output for L0-L3 on 2026-08-05, so
    escalation reclaims nothing. Without a terminal evict the window just overflows."""
    from headroom_proxy import compressor
    original_compress = compressor.compress
    compressor.compress = lambda text, level, query="", cls="": (text, "noop")
    try:
        window = 8000
        sess = controller.Session(id="tnoop", arm="adaptive", window=window)
        for t in range(1, 41):
            out = controller.handle(sess, fake_transcript(t), query=f"turn {t}")
            sent = sum(tokens.count(m["content"]) for m in out)
            assert sent <= window * 1.02, f"turn {t}: {sent} tokens over a {window} window"
        assert not sess.dead, "must survive a compressor whose levels do nothing"
    finally:
        compressor.compress = original_compress
    print("PASS no-op compressor: evicts instead of overflowing the window")


if __name__ == "__main__":
    test_passthrough()
    test_controller_40_turns()
    test_survives_noop_compressor()
    print("ALL PASS")
