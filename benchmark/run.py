"""Three-arm benchmark. One command: .venv/bin/python benchmark/run.py

Arm A (compact)  — direct + summarize-at-90%: what agent tools do today
Arm B (stock)    — stock Paritok fixed policy: tool results L1, history L3
Arm C (adaptive) — Headroom occupancy-targeted controller

Probes at turns 25/50/100 are FORKED: scored on the context as currently
rendered, never appended to the session (plan §4.3). Scoring = exact substring
match of the five pre-registered facts in benchmark/corpus.py.
"""

import json
import os
import sys
import time

os.environ.setdefault("HEADROOM_LOG", "logs/benchmark.jsonl")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from corpus import FACTS, PROBE_QUESTION, build_transcript  # noqa: E402
from headroom_proxy import controller, log, upstream  # noqa: E402

WINDOW = int(os.environ.get("HEADROOM_WINDOW", "32000"))
PROBE_TURNS = (25, 50, 100)
N_TURNS = 105
ARMS = {"A": "compact", "B": "stock", "C": "adaptive"}


def probe(rendered: list[dict]) -> dict:
    ctx = "\n".join(m["content"] for m in rendered)
    return {name: (fact in ctx) for name, fact in FACTS.items()}


def call_upstream(messages, sess, max_tokens=128, tag="turn"):
    """One real POST with honest logging; 429s back off, errors don't kill the run."""
    for attempt in range(4):
        t0 = time.time()
        try:
            resp = upstream.chat(messages, max_tokens=max_tokens)
            usage = resp.get("usage", {})
            log.write({"kind": "upstream", "session": sess.id, "arm": sess.arm,
                       "turn": sess.turn, "tag": tag,
                       "latency_ms": round(1000 * (time.time() - t0)),
                       "upstream": upstream.name(), "model": resp.get("model"),
                       "provider_prompt_tokens": usage.get("prompt_tokens"),
                       "provider_cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens")})
            return resp
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            log.write({"kind": "upstream_error", "session": sess.id, "arm": sess.arm,
                       "turn": sess.turn, "tag": tag, "status": status,
                       "error": str(e)[:200], "attempt": attempt})
            if status in (429, 502, 503):  # rate limit / upstream blip: back off
                time.sleep(5 * (attempt + 1))
            else:
                return None
    return None


def probe_model(rendered, sess):
    """The plan's §4.3 protocol, live: FORKED call (copy, never appended) asking
    the model to restate the constraints; exact-match scored on its reply."""
    if upstream.name() == "mock":
        return None
    resp = call_upstream(rendered + [{"role": "user", "content": PROBE_QUESTION}],
                         sess, max_tokens=512, tag="probe")
    if not resp:
        return None
    reply = resp["choices"][0]["message"]["content"] or ""
    return {name: (fact in reply) for name, fact in FACTS.items()}


def run_arm(arm: str) -> dict:
    sess = controller.Session(id=f"bench-{arm}", arm=arm, window=WINDOW)
    result = {"arm": arm, "probes": {}, "died_at": None, "cum_sent": 0, "turns": 0}
    for t, msgs in build_transcript(N_TURNS):
        rendered = controller.handle(sess, msgs, query=msgs[-2]["content"][:400])
        # ponytail: per-turn POSTs prove real upstream traffic but their replies are
        # discarded — nothing downstream reads them. HEADROOM_TURN_UPSTREAM=off skips
        # them so the 9 probe calls (where the model's answer IS the measurement) still
        # get through a rate-limited free tier. Leave it on when the budget allows.
        if os.environ.get("HEADROOM_TURN_UPSTREAM", "on") != "off":
            call_upstream(rendered, sess)  # the real POST; mock offline, SleepyAI with a key
        result["turns"] = t
        if t in PROBE_TURNS:
            scores = probe(rendered)
            model_scores = probe_model(rendered, sess)
            result["probes"][t] = scores
            if model_scores:
                result.setdefault("probes_model", {})[t] = model_scores
            log.write({"kind": "probe", "session": sess.id, "arm": arm, "turn": t,
                       "epoch": sess.epoch, "facts": scores,
                       "retained": sum(scores.values()),
                       "facts_model_restated": model_scores,
                       "retained_model": sum(model_scores.values()) if model_scores else None,
                       "question": PROBE_QUESTION})
        if sess.dead:
            result["died_at"] = t
            break
    result["epochs"] = sess.epoch
    # persist segment store for the dashboard's inspector
    dump_path = os.environ.get("HEADROOM_SEGMENTS", "logs/segments.json")
    existing = json.load(open(dump_path)) if os.path.exists(dump_path) else {}
    for seg in sess.store.by_id.values():
        existing[seg.id] = {
            "id": seg.id, "class": seg.cls, "priority": seg.priority,
            "arrival_turn": seg.arrival_turn, "original": seg.original,
            "reps": {lvl: {"text": txt, "tokens": n, "backend": b}
                     for lvl, (txt, n, b) in seg.reps.items()},
        }
    json.dump(existing, open(dump_path, "w"))
    return result


def main():
    if os.path.exists(log.LOG_PATH):
        os.rename(log.LOG_PATH, log.LOG_PATH + f".{int(time.time())}.bak")
    seg_path = os.environ.get("HEADROOM_SEGMENTS", "logs/segments.json")
    if os.path.exists(seg_path):
        os.remove(seg_path)

    results = {}
    for label, arm in ARMS.items():
        t0 = time.time()
        results[label] = run_arm(arm)
        print(f"Arm {label} ({arm}): {results[label]['turns']} turns, "
              f"probes {[(t, sum(p.values())) for t, p in results[label]['probes'].items()]}, "
              f"epochs={results[label]['epochs']}, "
              f"died_at={results[label]['died_at']}, {time.time() - t0:.1f}s")

    # everything below is read back OUT OF THE LOG, per the plan's ground rule
    rows = log.read_all()
    for label, arm in ARMS.items():
        req = [r for r in rows if r.get("arm") == arm and r.get("kind") == "request"]
        results[label]["avg_sent"] = round(sum(r["sent_tokens"] for r in req) / len(req))
        results[label]["cum_sent"] = sum(r["sent_tokens"] for r in req)
        results[label]["peak_occupancy_pct"] = max(r["occupancy_pct"] for r in req)
        results[label]["cache_stable_total"] = sum(r["cache_stable_prefix_tokens"] for r in req)

    json.dump({"window": WINDOW, "n_turns": N_TURNS, "facts": FACTS,
               "results": results}, open(os.environ.get("HEADROOM_LOG", "logs/benchmark.jsonl")
                        .rsplit(".jsonl", 1)[0] + "_summary.json", "w"), indent=2)
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
