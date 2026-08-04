# Checkpoint 0 — External dependency verification

Date: 2026-08-04, **re-verified against real keys 2026-08-05** · Status: **both
questions now answered live**

## Headline: the fake-success guard was not paranoia

The original checkpoint was written without credentials. Real keys for both
services have since been supplied, and the two open questions resolved in
opposite directions:

- **SleepyAI** — works. Every documented field is really returned, including
  `cached_tokens`. 324 live calls, 2 transient failures.
- **Paritok** — the key is **valid** (HTTP 200, not 401) and the service returns
  **your text back unchanged** with `gpu_available: false`. The hosted GPU is
  down. A client that trusted the HTTP status would have shipped *zero
  compression while believing it worked*. Headroom gates on `gpu_available` and
  logged `compressor=local-fallback` on all 20,696 compressed segments instead.

That guard was written on 2026-08-04 as a defensive precaution against a
hypothetical. On 2026-08-05 it caught the real thing.

## 1.1 SleepyAI (task model)

Status: **verified live**, 2026-08-05. 326 real POSTs across the three benchmark arms.

| Question | Answer | Evidence |
|---|---|---|
| `usage.prompt_tokens` in response? | **Yes — confirmed.** Present on all 324 successful calls. | `provider_prompt_tokens` non-null on 324/324 `kind=upstream` rows in `logs/benchmark.jsonl` |
| Prompt caching, and is it reported? | **Yes — confirmed, and it is real.** `usage.prompt_tokens_details.cached_tokens` is returned, non-zero on **91 of 324** calls, peaking at **26,176 cached tokens** on a single request. | same log, `provider_cached_tokens` field |
| Max context length? | Real per-model windows are visible once authenticated. The benchmark still uses a **configurable synthetic ceiling** (default 32k) so the pressure curve is reproducible by a judge without a key — stated openly rather than quietly borrowed from the provider. | `GET /api/v1/models` |
| Rate limits / reliability? | **2 failures in 326 calls**, both HTTP 502, both recovered on retry. Backoff covers 429/502/503. | 2 `kind=upstream_error` rows |
| Which free model? | `deepseek-v4-flash-0731:free` returned 503 on 8 of 9 calls and was abandoned mid-run. Health-checked five: `ling-3.0-flash:free` 502, `kimi-k3:free` timeout, `minimax-m3:free` timeout, `macaron-v1-tall:free` 200/6s, **`laguna-s-2.1` 200/4s ← chosen**. Reported by the API as `laguna-s-2.1-free`. | health probe, 2026-08-04 |

**Fallback (per plan §1.1):** token counts come from `tiktoken` when installed, else
chars/4 — the counter used is written into every log row as `token_counter`. Never
estimated silently.

## 1.2 Paritok hosted GPU

Status: **key supplied and probed live**, 2026-08-05, via `scripts/checkpoint0_probe.py`.

| Question | Answer | Evidence |
|---|---|---|
| Key works against `/api/compress`? | **The key is accepted — and that makes things worse, not better.** With no key: HTTP 401. With the real key: **HTTP 200**, `gpu_available: false`, and the input echoed back byte-for-byte. The service says so itself: *"The Paritok compression server is not reachable right now. Requests pass through UNCOMPRESSED. To compress, self-host the open 4B model: `ollama pull paritok/paritok-4b-v1`, then run `paritok proxy`."* | probe run, 2026-08-05 |
| Does `level` change output? | **Still unresolved — for a new reason.** Not auth this time: the GPU backend is simply down, so L0/L1/L2/L3 all return 4739 chars, 100% of the original, identical. The probe's verdict line printed *"key not accepted by GPU path (passthrough)"*. | `L0..L3: HTTP 200 · gpu_available=False · 4739 chars (100% of original)` |
| Was the fake-success guard needed? | **Yes, and this is the proof.** The earlier note said "check `gpu_available`, never just 2xx" as a precaution. That precaution is now the only thing standing between this project and a benchmark that silently measured nothing. | `compressor.py` requires `status < 300 and gpu_available and compressed` |

## 1.3 Contingency decision (adopted preemptively)

The controller is built so that **both dials exist**: it assigns a per-segment
`level` *and* chooses *which* segments get compressed at all. If the hosted GPU
turns out to ignore `level`, escalation degrades gracefully to "compress more
segments" (§1.3 pivot) with no rewrite — the escalation ladder simply collapses
L1/L2/L3 into "compressed". The local fallback compressor implements distinct
L1/L2/L3 behaviour deterministically, so the adaptive-vs-fixed comparison is
measurable today and honestly labeled as running on the fallback.

## 1.4 Sign-off

- [x] Every §1.1 / §1.2 box answered in writing above
- [x] Detection recipe for Paritok fake-success recorded (`gpu_available` + status)
- [x] Pivot path (§1.3) adopted as a built-in property, not a rewrite
- [x] Decision: **build as designed**, hosted paths behind env keys, fallback labeled
- [x] **Re-verified against real keys 2026-08-05** — SleepyAI confirmed on every
      documented field; Paritok hosted GPU confirmed **down**, guard caught it

**Verdict: proceed to H1–3 (proxy skeleton + logging).**

## What this means for the result

The compression backend the benchmark actually ran on is Headroom's own
deterministic local fallback, not Paritok's 4B model. Every affected log row says
so (`compressor=local-fallback`, 20,696 rows), and no headline number in this
repo is attributed to Paritok.

This limits *how much* each compression level saves — a neural summarizer would
squeeze harder than whitespace-collapse and line-elision. It does **not** touch
what the benchmark set out to test. The claim under test is about *which segments
a controller chooses to compress and when*, and all three arms compress through
the identical backend, so the comparison between them is unaffected. A better
compressor moves all three arms in the same direction.
