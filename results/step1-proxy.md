# Step 1 report — Proxy skeleton + logging (H1–3)

Status: **milestone met.** An agent pointed at the proxy behaves exactly as if it
weren't there (`X-Headroom-Arm: off` → byte-passthrough), and every upstream call
writes log rows first.

## What was built

| File | Role |
|---|---|
| `src/headroom_proxy/log.py` | JSONL log, one row per segment per upstream POST + one `request` row + one `upstream` row. Thread-safe append. `HEADROOM_LOG` overrides path. |
| `src/headroom_proxy/tokens.py` | `tiktoken/cl100k_base` when installed (it is, in `.venv`), else chars/4 — the active counter name is stamped into **every log row** (`token_counter`), so estimates are never silent. |
| `src/headroom_proxy/app.py` | FastAPI `POST /v1/chat/completions`, forwards to upstream, returns response unchanged. Non-streaming only, per plan. Plus `/api/log`, `/api/segment/{id}`, `/health`, `/` (dashboard). |
| `src/headroom_proxy/upstream.py` | SleepyAI client behind `SLEEPY_AI_API_KEY`; deterministic offline mock otherwise. Mock `usage` is flagged `"estimated": true`. |

## Log row schema (plan §2, adapted)

Segment rows: `ts · kind=segment · session · arm · turn · epoch · segment_id ·
class · priority · assigned_level · original_tokens · sent_tokens ·
was_recompressed · compressor · token_counter`.
Request rows add `occupancy_pct`, `window`, `cache_stable_prefix_tokens`, `dead`.
Upstream rows add `latency_ms`, `provider_prompt_tokens`, `upstream`.

Deviation from the plan's row sketch, disclosed: `latency_ms` and
`provider_prompt_tokens` live on the per-POST `upstream` row rather than being
duplicated onto every segment row; `cache_hit_estimated` is realized as
`cache_stable_prefix_tokens` (tokens of byte-identical rendered prefix vs the
previous POST — a measurable proxy for prefix-cache reuse).

## Verification

`tests/test_headroom.py::test_passthrough` — request via the real ASGI request
path returns an OpenAI-shaped response with `usage`, and the upstream row is in
the log. **PASS.**

## Arm routing (built here, used by the benchmark)

`X-Headroom-Arm: adaptive | stock | compact | off` selects the policy per
request; `X-Headroom-Session` keys the session store. This is how the three-arm
benchmark drives one proxy with identical traffic.
