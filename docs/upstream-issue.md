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

## Third: `level` semantics are still undocumented

We could not confirm from the hosted API whether `level` is honored at all —
the GPU was down for our entire window, so all four levels returned identical
passthrough. `level: "BANANA"` is also accepted by the schema. Recommend
rejecting unknown levels and documenting the per-level contract; it's the
single input any selector depends on.

## Proposal

1. Ship a minimal occupancy selector behind a config flag: watermarks +
   priority order (tool output < file reads < user turns < system), escalating
   only under pressure. Headroom's controller (~150 lines, Apache 2.0) is yours
   to take.
2. Make GPU-unavailable a non-2xx, or stop echoing the input into `compressed`.
3. Document hosted `level` semantics.

Raw logs (every number above traces to a row): `examples/run-2026-08-04/`.
