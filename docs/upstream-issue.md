# Draft GitHub issue for Paritok (tag: `hackathon-feedback`)

> **Title: The `level` dial is fully wired but nothing ever selects a value — proposal: an occupancy-based level selector (with measurements)**

`server.py` implements compression levels end to end: the dial exists, is wired
to the model, and callers can pass it. But nothing ever *chooses* between
values — tool results always take the default L1 and history is hardcoded to
L3. Turn 3 of a session gets crushed to L3 just as hard when the window is 20%
full as when it's 95% full. That's fidelity spent for no reason.

## What a selector buys (measured)

We built one on top of Paritok for the Build-with-Paritok hackathon
([Headroom](../README.md)) and measured fixed-vs-selected levels under
identical traffic — a scripted 105-turn debugging session, five facts planted
in the turn-1 briefing, forked probes, exact-substring scoring:

| Policy | Turns survived | Facts@25 | Facts@50 | Facts@100 | Peak occupancy |
|---|---|---|---|---|---|
| Fixed (tool L1 / history L3, stock) | 105 | 0/5 | 0/5 | 0/5 | **43.9%** |
| Occupancy-selected (watermarks 50/70/85%) | 105 | 5/5 | 5/5 | 5/5 | 79.6% |

The fixed policy's peak occupancy of 43.9% is the point: it compressed the
operator's briefing to L3 **while the window was less than half full**. A
selector that escalates lowest-priority segments first, only under watermark
pressure, retained all five facts at identical survival — needing exactly one
re-plan (one prefix-cache miss) all session.

Caveat we want to be upfront about: our arm ran on a deterministic local
fallback compressor, not the hosted GPU (see reproducer below); the *mechanism*
(when to compress what, and how hard) is independent of which compressor
executes the level.

## Second finding, and we think the more urgent one: a valid key + a down GPU returns HTTP 200 with your text unchanged

Reproducer against `https://www.paritok.com/api/compress`:

**Without a key** (2026-08-04) → HTTP **401**, `gpu_available: false`, content
echoed verbatim. Fine; loud and obvious.

**With a valid key** (2026-08-05) → HTTP **200**, `gpu_available: false`,
content echoed verbatim, identical at every level:

```
L0: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L1: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L2: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
L3: HTTP 200 · gpu_available=False · 4739 chars (100% of original)
```

```json
{"gpu_available": false,
 "message": "The Paritok compression server is not reachable right now. Requests pass through UNCOMPRESSED. To compress, self-host the open 4B model: `ollama pull paritok/paritok-4b-v1`, then run `paritok proxy`",
 "compressed": "<your input, byte for byte>"}
```

The failure is honest in the body and invisible in the envelope. A client doing
the obvious thing — `if resp.ok: use(resp.json()["compressed"])` — ships
uncompressed text believing it compressed, indefinitely, with no error to alert
on. In our case it would have meant an entire benchmark reporting savings that
never happened. We only caught it because we had written a `gpu_available` gate
as a precaution the day before, against a hypothetical.

Suggested fixes, roughly in order of value:

1. **Return a non-2xx when the GPU is unavailable** — 503 fits exactly. Any
   client's existing error path then handles it for free.
2. If passthrough must stay 200 for compatibility, at minimum **omit or null
   `compressed`** rather than filling it with the input, so the naive read
   fails loudly instead of silently succeeding.
3. Put `gpu_available` in the quickstart's first code sample, not just the
   schema. Every client needs this check and it isn't discoverable today.

## Third: two sharp edges on the self-host path you recommend

Your passthrough message points at `ollama pull paritok/paritok-4b-v1` + `paritok
proxy`. We took that path. The model pulls fine; `paritok proxy` we could not
find publicly installable (a link in that message would help). Driving the
weights directly, two things bit us that will bite everyone:

1. **Through ollama's `/api/generate` the model autocompletes instead of
   compressing.** Fed 12 lines of log frames it generated frames 12, 13, 14 and
   kept going to the timeout — 131% of the input, every identifier lost. The
   model ships ChatML stop tokens and the raw endpoint doesn't apply the
   template; `/api/chat` behaves correctly. Worth one line in the docs.
2. **Cold load is ~200s** for the 3.8 GB resident size, which silently blew our
   first three 300s timeouts. Warm it runs ~55 tok/s. Recommend suggesting a
   `keep_alive`.

With those handled, `level` clearly *is* honored — on a 556-char input we get
32% / 24% / 19% for L1/L2/L3, three distinct outputs. But on a realistic
1330-token input (stack trace + 60 repetitive log lines) it goes non-monotonic:

| Level | Output size | Time | Identifiers preserved |
|---|---|---|---|
| L1 | **100%** (no compression) | **84.4s** | 3/3 |
| L2 | **0.7%** (9 tokens) | 0.7s | **0/3** |
| L3 | 2% (31 tokens) | 1.4s | 1/3 |

L1 costs 84 seconds to do nothing, and L2 discards the entire content including
the file path, error code and version pin. If the ladder is meant to be graded,
this input breaks it. Happy to share the exact sample.

Separately: `level: "BANANA"` is accepted by the schema. Recommend rejecting
unknown levels and documenting the per-level contract — it's the single input
any selector depends on.

## Proposal

1. Ship a minimal occupancy selector behind a config flag: watermarks +
   priority order (tool output < file reads < user turns < system), escalating
   only under pressure. Headroom's controller (~150 lines, Apache 2.0) is yours
   to take.
2. Make GPU-unavailable a non-2xx, or stop echoing the input into `compressed`.
3. Document hosted `level` semantics.

Raw logs (every number above traces to a row): `examples/run-2026-08-04/`.
