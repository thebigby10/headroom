"""Does the Paritok 4B model honor `level`? — the question the hosted GPU couldn't answer.

The hosted service returns 200 + verbatim passthrough with `gpu_available: false`,
and points at a self-host path instead. This runs that path:

    ollama pull paritok/paritok-4b-v1
    PARITOK_OLLAMA_MODEL=paritok/paritok-4b-v1 .venv/bin/python scripts/paritok_local_probe.py

Measures two things per level: how much smaller the output is, and whether the
identifiers Headroom exists to protect survived. A compressor that shrinks text
by dropping the error code is not a win.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from headroom_proxy import compressor, tokens  # noqa: E402  (also loads .env)

# same shape as the benchmark corpus: a tool output with facts buried in it
MUST_SURVIVE = ["src/adapters/legacy_parser.py", "E_CONN_4471", "psycopg 2.9.3"]
SAMPLE = "\n".join(
    [
        "Traceback (most recent call last):",
        '  File "src/adapters/legacy_parser.py", line 214, in _drain',
        "    raise ConnectionError(code=E_CONN_4471)",
        "ConnectionError: pool exhausted talking to the replica",
        "",
        "Environment: psycopg 2.9.3, python 3.12.1, 4 workers",
        "",
    ]
    + [f"  frame {i}: worker_{i % 4} idle=0.0{i}s queued={i * 3} retries=0"
       for i in range(60)]
)
QUERY = "why is the legacy parser exhausting the connection pool"


def main():
    model = os.environ.get("PARITOK_OLLAMA_MODEL")
    if not model:
        sys.exit("set PARITOK_OLLAMA_MODEL (e.g. paritok/paritok-4b-v1)")

    base = tokens.count(SAMPLE)
    print(f"model={model}  original={base} tokens, {len(SAMPLE)} chars\n")
    outs = {}
    for level in ("L1", "L2", "L3"):
        t0 = time.time()
        out = compressor.compress_ollama(SAMPLE, level, QUERY)
        dt = time.time() - t0
        if out is None:
            print(f"{level}: FAILED (no response from ollama)")
            continue
        outs[level] = out
        n = tokens.count(out)
        kept = [f for f in MUST_SURVIVE if f in out]
        print(f"{level}: {n:5d} tokens ({100 * n // base:3d}% of original)  "
              f"{dt:5.1f}s  facts kept {len(kept)}/{len(MUST_SURVIVE)}"
              + ("" if len(kept) == len(MUST_SURVIVE)
                 else f"  LOST: {[f for f in MUST_SURVIVE if f not in out]}"))

    distinct = len({outs[k] for k in outs})
    print()
    if len(outs) < 3:
        print("VERDICT: incomplete — at least one level failed to return.")
    elif distinct == 1:
        print("VERDICT: `level` is a NO-OP on the local model too — all three "
              "levels returned identical text. Pivot per plan §1.3.")
    else:
        print(f"VERDICT: `level` WORKS — {distinct}/3 levels returned distinct "
              "output. This is the answer checkpoint 0 could not get from the "
              "hosted GPU.")


if __name__ == "__main__":
    main()
