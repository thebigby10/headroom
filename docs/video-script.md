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
what they remember. Two things I'm not claiming: Headroom doesn't send fewer
tokens than stock — it deliberately spends window on fidelity. And this run
used our deterministic fallback compressor and offline mock model — every log
row says so, and dropping in real keys is two env vars."

**2:40–3:00 — close.**
Screen: repo. "Apache 2.0, built with Paritok's hosted compression API, every
number on screen traceable to a log row. Repo and instant demo in the
description."
