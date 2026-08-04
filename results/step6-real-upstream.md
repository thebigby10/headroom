# Step 6 — Real upstream, real keys

Date: 2026-08-05 · Status: **complete for SleepyAI; Paritok hosted path confirmed down**

Everything before this step ran against a deterministic offline mock. This step
replaced the mock with a real model, re-ran all three arms live, and probed the
Paritok key that had been missing since Checkpoint 0. The two services came back
with opposite answers.

## What changed in the code

| File | Change | Why |
|---|---|---|
| `src/headroom_proxy/__init__.py` | minimal `.env` loader (real env always wins) | so proxy and benchmark pick up keys without a new dependency |
| `src/headroom_proxy/upstream.py` | `HEADROOM_MODEL` env override, default moved to `laguna-s-2.1` | the documented free default was returning 503 |
| `benchmark/run.py` | `call_upstream()` with retry + honest error logging; `probe_model()` | a 502 mid-run must not silently truncate an arm, and must not be hidden |
| `benchmark/run.py` | 502/503 added to the backoff list | observed, not anticipated |
| `tests/test_headroom.py` | pop both keys *after* the `.env`-loading import | tests hit the live API and failed 403 once the real key landed |

`probe_model()` implements the plan's §4.3 protocol properly for the first time:
a **forked** call — the probe question is appended to a *copy* of the rendered
context, sent, scored, and thrown away. The session never sees it, so measuring
does not perturb what is being measured.

## Picking a model

The documented free default, `deepseek-v4-flash-0731:free`, returned **503 on 8 of
its first 9 calls**. The run was stopped rather than reported as a result. Five
free models were health-checked:

| Model | Result |
|---|---|
| `deepseek-v4-flash-0731:free` | 503 (8/9 calls) |
| `ling-3.0-flash:free` | 502 |
| `kimi-k3:free` | timeout |
| `minimax-m3:free` | timeout |
| `macaron-v1-tall:free` | 200, ~6s |
| **`laguna-s-2.1`** | **200, ~4s ← chosen** |

## The live run

326 POSTs. **2 failures, both HTTP 502, both recovered on retry.** Every
documented `usage` field really arrives:

- `usage.prompt_tokens` — present on **324/324** successful calls
- `usage.prompt_tokens_details.cached_tokens` — non-zero on **91 of 324**,
  peaking at **26,176 cached tokens** on a single request

That last number matters beyond bookkeeping: it is direct evidence that the
provider's prefix cache is real and that Headroom's byte-stable rendering is
hitting it. The epoch design — treat a re-plan as a deliberate, counted cache
miss — is built on the assumption that a stable prefix gets cached. It does.

## Results

Unchanged in the first column, and that is the expected result rather than a
suspicious one: the corpus is a scripted transcript, so context construction is
deterministic and independent of what the model replies. Going live cannot move
context-presence numbers. What it adds is the model-restatement column.

| Arm | Turns | Facts in context @25/50/100 | Model restated @25/50/100 | Avg tok/turn | Peak occ. | Epochs |
|---|---|---|---|---|---|---|
| A compact | 105 | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 5,647 | 88.6% | — |
| B stock | 105 | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 7,876 | 43.9% | — |
| C **adaptive** | 105 | **5/5 · 5/5 · 5/5** | **2/5 · 3/5 · 4/5** | 16,464 | 79.6% | **1** |

**The honest reading of the new column.** Arm C holds all five facts in context
at every probe but the model restates only 2, then 3, then 4 of them. Context
presence is necessary, not sufficient — keeping a fact in the window does not
force the model to use it. The comparison survives that caveat intact, because A
and B score **0/5 at every checkpoint**: they cannot restate what is no longer
there. The gap between "in context" and "restated" is a real limitation of the
approach and is reported as one. C's rise from 2 to 4 across the session is one
run on one seed with no mechanism established; it is in the log, so it is
reported, but it should not be quoted as a trend.

## Paritok: the guard earned its keep

A real `PARITOK_API_KEY` was supplied and run through `scripts/checkpoint0_probe.py`.

```
L0: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L1: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L2: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L3: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
```

The key is **valid** — HTTP 200, not the 401 an absent key produced at Checkpoint
0. The service returns the input back byte-for-byte at every level and says why:

> "The Paritok compression server is not reachable right now. Requests pass
> through UNCOMPRESSED. To compress, self-host the open 4B model:
> `ollama pull paritok/paritok-4b-v1`, then run `paritok proxy`"

Checkpoint 0 had recorded, defensively, that a client must gate on
`gpu_available` and never on the HTTP status alone. That was written against a
hypothetical. It caught the real thing: a client trusting the 200 would have run
this entire benchmark measuring **zero compression while believing it worked**,
and every "saving" in the report would have been fabricated. Instead
`compressor.py` rejected the response and fell back, stamping
`compressor=local-fallback` on all 20,696 compressed segments.

**No headline number in this repo is attributed to Paritok.**

This limits how *hard* each level compresses — a learned 4B summarizer would
squeeze further than whitespace-collapse and line-elision. It does not touch the
claim under test. All three arms compress through the identical backend, so the
comparison between policies is unaffected; a better compressor moves all three
arms the same direction.

## Log integrity

Every number above reads back out of `logs/benchmark.jsonl` (35,430 rows), per the
project's ground rule that a number which cannot be read out of the log does not
count as a result.

| `kind` | Rows |
|---|---|
| `segment` | 34,780 |
| `upstream` | 324 |
| `request` | 315 |
| `probe` | 9 |
| `upstream_error` | 2 |

Backend attribution across segments: `none` 14,084 (L0, uncompressed by
definition) · `local-fallback` 20,696 · `paritok-gpu` **0**.
