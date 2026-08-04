"""Build examples/demo.html — the dashboard with the benchmark's log inlined,
so judges can open one file (or a static host) and see the real run with zero
setup. Same page code, same rows; only the transport changes.

Run: .venv/bin/python scripts/make_demo.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from headroom_proxy import log  # noqa: E402

TURN_STEP = 5
TRIM = 2500  # chars per stored text in the inlined segment store


def main():
    rows = log.read_all("logs/benchmark.jsonl")
    keep_turns = set(range(5, 106, TURN_STEP)) | {1, 25, 50, 100}
    out_rows, seg_ids = [], set()
    for r in rows:
        k = r.get("kind")
        if k in ("request", "probe"):
            out_rows.append(r)
        elif k == "segment" and r.get("turn") in keep_turns:
            out_rows.append(r)
            seg_ids.add(r["segment_id"])

    store = json.load(open("logs/segments.json"))
    segments = {}
    for sid in seg_ids:
        s = store.get(sid)
        if not s:
            continue
        segments[sid] = {**s, "original": s["original"][:TRIM],
                         "reps": {lvl: {**rep, "text": rep["text"][:TRIM]}
                                  for lvl, rep in s["reps"].items()}}

    data = {"log": out_rows,
            "summary": json.load(open("logs/benchmark_summary.json")),
            "segments": segments}
    html = open("dashboard/index.html").read()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("<script>",
                        f"<script>window.HEADROOM_DATA={blob};</script>\n<script>", 1)
    os.makedirs("examples", exist_ok=True)
    open("examples/demo.html", "w").write(html)
    print(f"examples/demo.html: {os.path.getsize('examples/demo.html') / 1e6:.1f} MB, "
          f"{len(out_rows)} rows, {len(segments)} segments")


if __name__ == "__main__":
    main()
