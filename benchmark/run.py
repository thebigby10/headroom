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


def run_arm(arm: str) -> dict:
    sess = controller.Session(id=f"bench-{arm}", arm=arm, window=WINDOW)
    result = {"arm": arm, "probes": {}, "died_at": None, "cum_sent": 0, "turns": 0}
    for t, msgs in build_transcript(N_TURNS):
        rendered = controller.handle(sess, msgs, query=msgs[-2]["content"][:400])
        upstream.chat(rendered)  # the real POST; mock offline, SleepyAI with a key
        sent = sum(r["sent_tokens"] for r in [])  # totals come from the log, not here
        result["turns"] = t
        if t in PROBE_TURNS:
            scores = probe(rendered)
            result["probes"][t] = scores
            log.write({"kind": "probe", "session": sess.id, "arm": arm, "turn": t,
                       "epoch": sess.epoch, "facts": scores,
                       "retained": sum(scores.values()), "question": PROBE_QUESTION})
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
               "results": results}, open("logs/benchmark_summary.json", "w"), indent=2)
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
