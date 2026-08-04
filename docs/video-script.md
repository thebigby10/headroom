# Video script (hard limit 3:00)

**0:00–0:25 — the failure, first.**
Screen: Arm A in the dashboard, scrubbing past turn 25. "This is a normal
debugging session. At turn 25 the tool compacted the conversation. These five
chips are the operator's original constraints — file path, latency budget, a
do-not-touch directory, a version pin, an error code. All five: gone. The agent
keeps going, confidently, slightly wrong."

**0:25–1:00 — what Headroom is.**
Screen: terminal, one line: `export OPENAI_BASE_URL=http://127.0.0.1:8791/v1`.
"One base-URL change, no SDK, no rewrite. Headroom watches how full the window
is. While there's room it does nothing at all. Watch the occupancy bar fill."

**1:00–2:00 — the money shot.**
Screen: Arm C, slider from 1 to 105. "Turn 9: occupancy crosses the watermark —
one epoch fires. Tool output gets crushed to L3, file reads to L2, and the
operator's words are never touched. The fact counter: five out of five. Turn
50: five out of five. Turn 100: five out of five. Now the same session through
stock fixed-level compression—" switch to Arm B "—zero out of five, and its
peak occupancy was 43% — it burned that fidelity when the window was half
empty."

**2:00–2:40 — the table, and the honest part.**
Screen: three-arm table. "Same survival on all three arms — the difference is
what they remember. The shaded columns are the strict test: a real model asked
to restate the constraints. Headroom gets 2, then 3, then 4 of 5 — not perfect,
and I'm showing you that. The other two get zero at every probe, because you
can't restate what you threw away.

Two things I'm not claiming. Headroom doesn't send fewer tokens — it sends
almost three times Arm A's, deliberately spending window on fidelity. And the
compression here is our own fallback, not Paritok's model: their hosted GPU was
down all weekend, and it fails by returning HTTP 200 with your text unchanged.
We caught it because we gate on their `gpu_available` flag instead of the status
code. Every affected log row says `local-fallback`; no number here is credited
to Paritok."

**2:40–3:00 — close.**
Screen: repo. "Apache 2.0, every number on screen traceable to a log row —
including the ones that don't flatter us. Repo and instant demo in the
description."
