"""Checkpoint 0 probe: does the hosted Paritok GPU honor `level`?

Run when PARITOK_API_KEY is set: .venv/bin/python scripts/checkpoint0_probe.py
Sends identical content at L0 and L3 and diffs the results. This is the single
biggest open risk in the project (see results/checkpoint0.md).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import httpx  # noqa: E402

from headroom_proxy.compressor import PARITOK_ENDPOINT  # noqa: E402  (also loads .env)

SAMPLE = "\n".join(
    f"def handler_{i}(batch):\n    # normalize partner records, stage {i}\n"
    f"    return [transform(r, mode={i % 3}) for r in batch.rows]" for i in range(40))


def call(level):
    r = httpx.post(PARITOK_ENDPOINT,
                   headers={"Authorization": f"Bearer {os.environ['PARITOK_API_KEY']}"},
                   json={"content": SAMPLE, "query": "fix the normalizer",
                         "kind": "file_read", "level": level}, timeout=60)
    body = r.json()
    return r.status_code, body.get("gpu_available"), body.get("compressed", "")


def main():
    if not os.environ.get("PARITOK_API_KEY"):
        sys.exit("PARITOK_API_KEY not set (put it in .env)")
    results = {lvl: call(lvl) for lvl in ("L0", "L1", "L2", "L3")}
    for lvl, (status, gpu, text) in results.items():
        print(f"{lvl}: HTTP {status} · gpu_available={gpu} · {len(text)} chars "
              f"({100 * len(text) // len(SAMPLE)}% of original)")
    l0, l3 = results["L0"][2], results["L3"][2]
    if not results["L0"][1]:
        print("\nVERDICT: key not accepted by GPU path (passthrough) — check dashboard attribution")
    elif l0 == l3:
        print("\nVERDICT: level is a NO-OP on the hosted path — pivot per plan §1.3 "
              "(controller degrades gracefully: escalation = compress more segments)")
    else:
        print(f"\nVERDICT: level WORKS — L3 is {100 * len(l3) // max(len(l0), 1)}% "
              "the size of L0 output. Build as designed.")


if __name__ == "__main__":
    main()
