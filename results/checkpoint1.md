# Checkpoint 1 — Does adaptive beat stock on fidelity?

Date: 2026-08-04, **re-run against a live model 2026-08-05** · Verdict: **🟢 STRONG PASS**

> At equal session survival, does Headroom retain more of the early session than
> stock Paritok? **Yes: 5/5 planted facts at turns 25, 50 and 100, versus 0/5
> for stock and 0/5 for compaction — at identical survival (all arms complete
> all 105 turns), with exactly one epoch (one counted cache miss).**
>
> And when a **real model** is asked to restate those constraints from the
> context each arm actually built: **Headroom 2/5 → 3/5 → 4/5 at turns 25/50/100;
> stock and compaction 0/5 at every probe.**

## The run

One command: `.venv/bin/python benchmark/run.py`
Task: scripted 105-turn debugging session (`benchmark/corpus.py`, seeded RNG,
fully deterministic) — file reads, test runs, greps, hypothesis turns; ~2.5k
tokens/turn of inflow against a 32k window (~8× oversubscribed by turn 105).
Five facts planted mid-paragraph in the turn-1–3 briefing, **written before any
arm ran**, chosen to be exactly-reproducible-or-not (no LLM grader):
file path · 400ms latency constraint · vendor/ prohibition · psycopg 2.9.3 · E_CONN_4471.

Probes at 25/50/100 are **forked**: scored against the context as currently
rendered for upstream, never appended to the session (plan §4.3). Two probes run
at each checkpoint:

1. **Context presence** — is the fact's exact string still in the context being
   sent upstream? This is what the controller directly governs.
2. **Model restatement** — a real forked call to the task model asking it to
   restate the constraints; scored by exact substring on *its reply*. This is the
   stricter test: it asks whether the surviving context is good enough for the
   model to actually use.

## Results (every number reads back out of `logs/benchmark.jsonl` — 35,430 rows)

Upstream: **SleepyAI `laguna-s-2.1`**, 326 live calls, 2 transient 502s (both
recovered on retry).

| Arm | Policy | Turns survived | Context facts @25/50/100 | **Model restated @25/50/100** | Avg sent tok/turn | Peak occupancy | Epochs | Cache-stable prefix tokens (cum.) |
|---|---|---|---|---|---|---|---|---|
| A | direct + compact-at-90% | 105 (all) | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 5,647 | 88.6% | — | 243,183 |
| B | stock Paritok policy (tool L1, history L3) | 105 (all) | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 7,876 | 43.9% | — | 456,827 |
| C | **Headroom adaptive** | 105 (all) | **5/5 · 5/5 · 5/5** | **2/5 · 3/5 · 4/5** | 16,464 | 79.6% | **1** | 1,367,338 |

The context-presence numbers are unchanged from the offline run, and that is
expected rather than suspicious: the corpus is a scripted transcript, so context
construction is deterministic and does not depend on what the model replies.
Switching from mock to live upstream adds the model-restatement column and real
provider token accounting; it cannot move the first column.

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
- **Context presence is necessary but not sufficient.** C holds 5/5 in context at
  every probe but the live model restates only 2, then 3, then 4 of them. The gap
  is the honest part of this result: keeping a fact in the window does not
  guarantee the model uses it. What the comparison still shows cleanly is that A
  and B score **0/5 on this probe at every checkpoint** — they cannot restate what
  is no longer there, so for them the gap never even gets a chance to open.
- **C's model score rises with session length (2 → 3 → 4).** One run, one seed, and
  no mechanism established — reported because it is in the log, not because it is
  explained. It should not be quoted as a trend without more runs.

## Fixes the benchmark forced (found at H6, exactly as the plan intended)

1. Escalation originally bumped every class one ladder-step per round, so user
   turns hit lossy L2 while tool outputs still had headroom. Now lower-priority
   classes exhaust their ladders **before** a higher class loses a byte.
2. `file_read` moved to its own priority below `user` — a 3,700-token file read
   is more expendable than the operator's 380-token briefing.
3. Epochs only count when a re-plan actually changes a level; under-pressure
   arrivals adopt prevailing levels at the tail without busting the prefix.

## Disclosed limitations of this run

- **Compressor: local deterministic fallback — and now for a confirmed reason.**
  A real `PARITOK_API_KEY` *was* supplied and probed on 2026-08-05. The hosted
  GPU is down: it returns HTTP 200 with `gpu_available: false` and the input
  echoed back verbatim at every level (see `results/checkpoint0.md`). Headroom's
  guard caught it and fell back, stamping `compressor: local-fallback` on all
  20,696 compressed segments. Hosted L3 is a learned summarizer and may retain
  more than the fallback's head/tail heuristic — B's 0/5 could improve with a
  working GPU; C's 5/5 does not depend on the compressor at all, since its early
  user turns are never compressed. **No number in this repo is attributed to
  Paritok.**
- **Upstream: real.** SleepyAI `laguna-s-2.1`, 326 live calls, 2 transient 502s.
  `usage.prompt_tokens` returned on 324/324; `cached_tokens` non-zero on 91 of
  them, peaking at 26,176. Token counter `tiktoken/cl100k_base` stamped per row.
- **Scoring:** two probes, both exact-substring, no LLM grader — context presence
  (what the model *could* see) and live model restatement (what it actually
  repeated). Neither is a judgment call.
- **Cost: Arm C is not the cheap arm, and this table does not claim it is.** C
  sends ~2.9× A's tokens per turn and ~2.1× B's. The claim is fidelity at equal
  survival, not savings. The number that indicts stock policy is B's **43.9% peak
  occupancy**: it destroyed all five facts while leaving more than half the
  window unused — it compressed hard when there was no pressure to.
- One task, one seed. A demonstration, not a general law.

## Sign-off (plan §4.6)

- [x] All three arms run from one command
- [x] Facts + probe question written before any arm ran (in `corpus.py`, committed)
- [x] Arm B is the stock policy, unmodified (tool L1 / history L3, no occupancy logic)
- [x] This file contains the table and a clear verdict
- [x] Token figures: mock usage disclosed as estimated; counter named per-row
- [x] Decision: **Strong pass → dashboard next**
