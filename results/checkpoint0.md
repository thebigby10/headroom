# Checkpoint 0 — External dependency verification

Date: 2026-08-04 · Status: **answered in writing, with one blocker disclosed**

## Blocker disclosed up front

No `PARITOK_API_KEY` and no `SLEEPY_AI_API_KEY` exist on this machine (checked env,
shell configs, project `.env` files — only empty `.env.example` templates in the
sibling `universal-clipboard` project). Every checkbox below is answered as far as
it can be without credentials, and the build is arranged so that dropping real keys
into `.env` activates the hosted paths with **zero code changes**. Until then the
rig runs on a deterministic local fallback, clearly labeled in every log row
(`compressor=local-fallback`).

## 1.1 SleepyAI (task model)

| Question | Answer | Evidence |
|---|---|---|
| `usage.prompt_tokens` in response? | **Documented yes**, unverified — no key. Docs: "Usage data (including cached tokens) is included in the final response." | `GET /api/v1/models` → HTTP 401 `{"error":"Missing or invalid Authorization header"}` — endpoint live, auth enforced |
| Max context length? | Unknown without key. Per plan §9: benchmark uses a **configurable synthetic window ceiling** (default 32k tokens) and states so openly. | — |
| Prompt caching? | Documented yes (`cacheReadPrice`, "cache status reported transparently"), unverified. Epoch design holds either way; cache-miss column marked *estimated* until verified. | docs |
| Rate limits? | Plan-tier RPM + spending windows, numbers unknown. Mitigation already in design: sessions are recorded once and re-runs replay offline. | docs |

**Fallback (per plan §1.1):** token counts come from `tiktoken` when installed, else
chars/4 — the counter used is written into every log row as `token_counter`. Never
estimated silently.

## 1.2 Paritok hosted GPU

| Question | Answer | Evidence |
|---|---|---|
| Key works against `/api/compress`? | No key to test. **But the Segpilot claim "returns 200 for absent keys" is false today**: absent/invalid key → **HTTP 401** with `{"gpu_available": false, "message": "Invalid or missing Paritok API key — request passed through uncompressed."}` and the content echoed back verbatim. So a fake-success is detectable: check `gpu_available` and status code, never just 2xx. | live curl, 2026-08-04 |
| Does `level` change output? | **Untestable without a valid key** (uncompressed passthrough regardless of level; `level:"BANANA"` also 401-passthrough). This remains the project's biggest open risk — resolved the moment a key arrives by diffing L0 vs L3 on identical input (`scripts/checkpoint0_probe.py` does exactly this). | live curl |
| Latency / 10 parallel? | Unauthenticated round-trip ~1s. Real numbers pending key. | curl timing |

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

**Verdict: proceed to H1–3 (proxy skeleton + logging).**
