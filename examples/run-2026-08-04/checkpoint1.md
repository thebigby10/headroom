# Checkpoint 1 — Does adaptive beat stock on fidelity?

Date: 2026-08-04 · Verdict: **🟢 STRONG PASS** → build the dashboard.

> At equal session survival, does Headroom retain more of the early session than
> stock Paritok? **Yes: 5/5 planted facts at turns 25, 50 and 100, versus 0/5
> for stock and 0/5 for compaction — at identical survival (all arms complete
> all 105 turns), with exactly one epoch (one counted cache miss).**

## The run

One command: `.venv/bin/python benchmark/run.py`
Task: scripted 105-turn debugging session (`benchmark/corpus.py`, seeded RNG,
fully deterministic) — file reads, test runs, greps, hypothesis turns; ~2.5k
tokens/turn of inflow against a 32k window (~8× oversubscribed by turn 105).
Five facts planted mid-paragraph in the turn-1–3 briefing, **written before any
arm ran**, chosen to be exactly-reproducible-or-not (no LLM grader):
file path · 400ms latency constraint · vendor/ prohibition · psycopg 2.9.3 · E_CONN_4471.

Probes at 25/50/100 are **forked**: scored against the context as currently
rendered for upstream, never appended to the session (plan §4.3).

## Results (every number reads back out of `logs/benchmark.jsonl` — 35,104 rows)

| Arm | Policy | Turns survived | Facts@25 | Facts@50 | Facts@100 | Avg sent tok/turn | Peak occupancy | Epochs | Cache-stable prefix tokens (cum.) |
|---|---|---|---|---|---|---|---|---|---|
| A | direct + compact-at-90% | 105 (all) | 0/5 | 0/5 | 0/5 | 5,647 | 88.6% | — | 243,183 |
| B | stock Paritok policy (tool L1, history L3) | 105 (all) | 0/5 | 0/5 | 0/5 | 7,876 | 43.9% | — | 456,827 |
| C | **Headroom adaptive** | 105 (all) | **5/5** | **5/5** | **5/5** | 16,464 | 79.6% | **1** | 1,367,338 |

Reading the table honestly:

- **The claim held in its exact form** — *same survival, better fidelity*. C does
  **not** win on tokens: stock B sends less than half as much per turn (7.9k vs
  16.5k). C deliberately spends window it has on fidelity it can keep. That
  trade is the entire thesis, stated up front in the project idea (§4).
- **B's peak occupancy of 43.9%** is the mechanism's indictment of fixed policy:
  stock crushed the briefing to L3 when the window was *less than half full* —
  fidelity spent for no reason. C stayed at L0 for user turns the whole session
  because escalating file reads and tool outputs was always enough.
- **One epoch.** The first watermark crossing (turn 9) L3'd tool outputs and
  L2'd file reads; new arrivals adopt the prevailing class level at the tail
  (an append, not a prefix rewrite), so no further re-plan was ever needed.
  C's cumulative byte-stable prefix (1.37M tokens) is 3× B's — the epoch design
  doing what §6 promised.
- **Arm A survives by amnesia**: repeated compaction keeps it alive forever and
  it forgets everything early — 0/5 by turn 25. Survival alone was the wrong
  metric; this is why the benchmark measures fidelity at fixed survival.

## Fixes the benchmark forced (found at H6, exactly as the plan intended)

1. Escalation originally bumped every class one ladder-step per round, so user
   turns hit lossy L2 while tool outputs still had headroom. Now lower-priority
   classes exhaust their ladders **before** a higher class loses a byte.
2. `file_read` moved to its own priority below `user` — a 3,700-token file read
   is more expendable than the operator's 380-token briefing.
3. Epochs only count when a re-plan actually changes a level; under-pressure
   arrivals adopt prevailing levels at the tail without busting the prefix.

## Disclosed limitations of this run

- **Compressor:** local deterministic fallback (no Paritok key on this machine);
  every log row carries `compressor: local-fallback`. Hosted L3 is a learned
  summarizer and may retain more than the fallback's head/tail heuristic — B's
  0/5 could improve with a real key; C's 5/5 does not depend on the compressor
  since its early user turns are never compressed at all. Re-running with a key
  is one env var (`PARITOK_API_KEY`).
- **Upstream:** offline mock (no SleepyAI key); `usage` flagged `estimated`,
  token counter `tiktoken/cl100k_base` stamped in every row.
- **Scoring:** exact-substring presence in the sent context — measures what the
  model *could* see, not what it would repeat. Deliberate: reproducible, no grader.
- One task, one seed. A demonstration, not a general law.

## Sign-off (plan §4.6)

- [x] All three arms run from one command
- [x] Facts + probe question written before any arm ran (in `corpus.py`, committed)
- [x] Arm B is the stock policy, unmodified (tool L1 / history L3, no occupancy logic)
- [x] This file contains the table and a clear verdict
- [x] Token figures: mock usage disclosed as estimated; counter named per-row
- [x] Decision: **Strong pass → dashboard next**
