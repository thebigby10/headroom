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

## Also found at hour zero: hosted `level` behaviour is unverifiable for new users

Reproducer against `https://www.paritok.com/api/compress` (2026-08-04):

- No/invalid key → **HTTP 401** with `{"gpu_available": false, "message":
  "Invalid or missing Paritok API key — request passed through uncompressed."}`
  and the content echoed verbatim. (Good: this contradicts earlier community
  reports of silent 200s — but the passthrough-echo shape means a client that
  only checks for a `compressed` field will silently ship uncompressed text.
  Recommend clients be told to gate on `gpu_available`.)
- `level: "BANANA"` is accepted by the schema (401 for us, so we cannot confirm
  whether a valid key validates it). Recommend: reject unknown levels, and
  document whether the hosted path honors `level` at all — we could not find it
  documented, and it's the single input a selector depends on.

## Proposal

1. Ship a minimal occupancy selector behind a config flag: watermarks +
   priority order (tool output < file reads < user turns < system), escalating
   only under pressure. Headroom's controller (~150 lines, Apache 2.0) is yours
   to take.
2. Document hosted `level` semantics, and make `gpu_available` prominent in the
   quickstart so passthrough responses can't masquerade as compressed.

Raw logs (every number above traces to a row): `examples/run-2026-08-04/`.
