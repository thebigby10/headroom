# Submission plan

Status as of 2026-08-05. Numbers marked ⏳ depend on the hosted re-run in flight
(`logs/paritok-fixed.jsonl`); everything else is measured and final.

## The story changed — read this first

The submission was built around "Paritok's hosted GPU is down, so no number here
is credited to Paritok." That is no longer true. On 2026-08-05 the GPU came back
up and three things follow:

1. **Paritok really compresses.** Real corpus prose: 1,796 chars → 431. The
   probe corpus compresses to ~6% of original.
2. **`level` is a no-op on the hosted path.** L0/L1/L2/L3 return 302/289/302/302
   chars for the same input. The dial is accepted by the schema and discarded.
3. **That had teeth.** With hosted Paritok, escalation reclaimed nothing, so the
   controller had no floor and arms B and C overflowed the 32k window and died
   at turns 48 and 58. Fixed in `3ccb8c8` by evicting once every ladder is spent.

The honest framing is now *stronger*, not weaker: we integrated a compressor,
found its dial inert, detected it in-flight, and degraded correctly instead of
dying. That is the submission's spine.

## 1. Project URL

**https://thebigby10.github.io/headroom/** — live, verified 200.

Self-contained recorded run, no setup, no API key. `index.html` redirects to
`examples/demo.html` (2.9 MB, all data inlined).

## 2. Public repository

**https://github.com/thebigby10/headroom** — public, `Apache-2.0` detected in
the About box, homepage set, Paritok credited with badge and link in the README.

## 3. Paritok account

The email on the API key in `.env`. Dashboard usage will show the probe traffic
plus two full 3-arm benchmark runs — the run is genuinely hosted-GPU-backed, so
this now verifies cleanly.

## 4. Text description

> **Headroom** is an OpenAI-compatible proxy that compresses an agent's context
> by *occupancy* rather than by fixed policy. One environment variable —
> `OPENAI_BASE_URL` — and no SDK change. While the window has room it does
> nothing at all; when occupancy crosses a watermark it re-plans the whole
> layout in a single epoch, escalating lowest-priority segments first so a tool
> output reaches L3 before a user turn loses a byte.
>
> The problem: agent tools compact on a turn counter or a token ceiling, and
> when they do, the operator's original constraints — a file path, a latency
> budget, a do-not-touch directory — flatten into a summary and are gone. We
> planted five such constraints in a 105-turn debugging session and measured how
> many survived.
>
> **Where Paritok made the difference.** Paritok's hosted GPU does the actual
> compression for the segments that dominate token volume: tool output 198/198,
> file reads 175/175, search results 176/187 went through `paritok-gpu`. Short
> conversational turns come back empty and fall back to a local compressor —
> every log row is stamped with which backend produced it, so any number here is
> traceable to a compressor.
>
> **The most interesting thing we built wasn't planned.** Paritok's hosted API
> accepts a `level` parameter and ignores it — L0 and L3 return the same output.
> Our controller assumed escalation always reclaims space, so with a no-op dial
> it escalated everything, gained nothing, and overflowed the window; two of
> three arms died mid-session. The fix is a terminal eviction step once every
> ladder is exhausted, with evicted segments left as tombstones so message order
> survives and the model is told a segment is gone rather than having its
> history silently rewritten. We also found the hosted API returns HTTP 200 with
> `compressed: ""` on some inputs; we gate on the payload rather than the status
> code, which is how we caught it. Both are filed upstream.
>
> Stack: Python 3.12, FastAPI, httpx, tiktoken, Paritok hosted compression,
> SleepyAI as the task model. Apache-2.0.

## 5. Video script (hard limit 3:00)

**0:00–0:25 — the failure, first.**
Arm A in the dashboard, scrubbing past turn 25. "This is a normal debugging
session. At turn 25 the tool compacted the conversation. These five chips are
the operator's original constraints — file path, latency budget, a do-not-touch
directory, a version pin, an error code. All five: gone. The agent keeps going,
confidently, slightly wrong."

**0:25–0:55 — what Headroom is.**
Terminal, one line: `export OPENAI_BASE_URL=http://127.0.0.1:8791/v1`. "One
base-URL change, no SDK, no rewrite. Headroom watches how full the window is.
While there's room it does nothing at all. Watch the occupancy bar fill."

**0:55–1:45 — the money shot.**
Arm C, slider 1 → 105. "Turn 9: occupancy crosses the watermark — one epoch
fires. Tool output gets crushed, file reads compressed, and the operator's words
are never touched. The fact counter: five out of five. Turn 50: five out of
five. Turn 100 ⏳. Now the same session through stock fixed-level compression—"
switch to Arm B "—and its peak occupancy was 43% when it burned that fidelity.
It spent the window while the window was half empty."

**1:45–2:40 — the part that's actually interesting.**
"Here's what we didn't plan. Paritok's hosted API takes a compression level.
L0 through L3. Watch —" show the four probe lines "— 302 characters, 289, 302,
302. The dial does nothing. Our controller assumed compressing harder always
buys space, so it escalated everything, bought nothing, and blew through the
window. Two of three arms died mid-session, turn 48 and turn 58. The fix is a
floor: when every ladder is exhausted and we're still over, evict the
lowest-priority segments and leave a tombstone, so the model knows something's
missing instead of being quietly lied to. That's the run you're looking at."

**2:40–3:00 — close.**
Repo. "Every number on screen traces to a log row, including which compressor
produced it — Paritok's GPU or our fallback. Apache 2.0. Repo and instant demo
in the description."

**Recording notes:** no copyrighted music, no third-party trademarks. Upload
public to YouTube. The 1:45–2:40 block is what separates this from a wrapper
demo — do not cut it for time; cut from 0:25–0:55 instead.

## 6. Sample outputs

Already satisfied — `examples/` holds the recorded run (`benchmark.jsonl.gz`,
`benchmark_summary.json`, `checkpoint1.md`) and `demo.html`. Add
`examples/run-2026-08-05-hosted/` with the hosted run once it lands, so judges
can diff local-fallback against hosted-Paritok themselves.

## 7. Social post

`docs/social-post.md` — rewrite the hook around the `level` no-op rather than
the outage. Tag `#BuiltWithParitok`. Post to X or dev.to.

## Bonus: feedback prize

`docs/upstream-issue.md`, four findings, tag `hackathon-feedback`:

1. Fixed-level policy vs. an occupancy selector (measured)
2. `level` is a no-op on the hosted path
3. HTTP 200 with `compressed: ""` while the GPU is up
4. Self-host sharp edges (non-monotonic L1/L2 on the 4B weights)

File it **before** submitting so finding 2 and 3 are linkable from the text
description. One `<!-- TODO before filing -->` marker remains on the results
table's provenance line — resolve against the hosted re-run.

## Order of operations

1. ⏳ Hosted re-run finishes → confirm arms B and C survive to 105
2. Rewrite `README.md` disclosure — it still says the GPU is down (**false now**)
3. Rewrite `results/checkpoint0.md` and `results/checkpoint1.md` likewise
4. Regenerate `examples/demo.html` from the hosted run (`scripts/make_demo.py`)
5. Resolve the TODO in `docs/upstream-issue.md`, file it, copy the URL
6. Record video against the regenerated dashboard
7. Publish social post
8. Submit: URL, repo, Paritok email, description, video link, issue link

## Pre-submit checklist

- [ ] README says nothing untrue about Paritok's availability
- [ ] Every claimed number traces to a log row with a `compressor` stamp
- [ ] `examples/` contains both runs, local-fallback and hosted
- [ ] Pages URL still 200 after the demo regeneration
- [ ] Video is public, under 3:00, no copyrighted audio
- [ ] Upstream issue filed and linked
- [ ] `PARITOK_API_KEY` and `SLEEPY_AI_API_KEY` are not in any committed file
