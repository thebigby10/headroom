# Step 2 report — The controller (H3–6)

Status: **milestone met.** Synthetic 40-turn transcript through the controller:
occupancy stays under the ceiling, epochs fire, pinned content is byte-identical
at the end, and every representation derives from the stored original.

## The four pieces (plan §3, in order)

1. **Segment store** (`segments.py`). One segment per message, keyed by content
   hash. Keeps the **original text permanently**; per-level representations are
   cached, so unchanged epochs re-render byte-identically (prefix-cache friendly)
   and re-compression always runs original → level, never compressed → compressed.
2. **Occupancy accounting** (`controller.py::_occupancy`). Sum of
   currently-assigned representation tokens against the window ceiling
   (`HEADROOM_WINDOW`, default 32k — the synthetic ceiling adopted at
   Checkpoint 0 since SleepyAI's real max is unverifiable without a key).
3. **Level policy** (`_replan`). Walks non-pinned segments in (priority
   ascending, oldest first) order, escalating one ladder step per round until
   occupancy is under target. Pinned segments (system prompt, `[PINNED]`
   markers, last 2 exchanges + current turn) are skipped unconditionally.
4. **Epoch trigger.** Watermarks at 50% / 70% / 85%. Crossing one upward
   re-plans; nothing else does — with two refinements found by test:
   - Once above the top watermark, growth can trigger further re-plans
     (otherwise occupancy blows past the ceiling late-session).
   - An epoch is only *counted* when the re-plan actually changed a level —
     that is the moment the byte-prefix changes and the real cache miss occurs.
   - Each re-plan digs to (watermark − 0.20), buying many turns of slack so
     epochs stay rare instead of firing every turn under saturation.

## Class table (from PROJECT_IDEA §7)

`tool_output` prio 1 ladder L0→L1→L2→L3 · `search` prio 1 L0→L2→L3 ·
`user`/`file_read` prio 2 (→L2 max) · `assistant`/`tool_schema` prio 3 (→L1 max) ·
`system`/`pinned` never touched. Classification is a first-80-chars heuristic
(`TOOL OUTPUT:`, `FILE:`, `Search results`, role) — disclosed limitation: a
real-world classifier would use richer signals.

## Baseline arms live in the same file, same code path

- **stock** (Arm B): current-turn tool results → L1, all history → L3, always —
  Paritok's fixed default per the upstream `server.py` reading. Verified by test:
  L3 rows appear even with an effectively infinite window.
- **compact** (Arm A): no compression; at 90% occupancy replaces all but system +
  last 6 messages with a naive one-screen summary (what agent tools do today).

## Test evidence (`tests/test_headroom.py`)

40 turns, 8k window, ~28k tokens of original inflow (3.5× oversubscribed):
occupancy held under ceiling, **12 epochs** (bounded < turns/3 by regression
test; expected far fewer at the benchmark's 32k window until late saturation),
pinned system prompt byte-identical after 40 turns, all L0 reps equal originals.

## Open risk carried forward

Local fallback compressor implements L1/L2/L3 deterministically; hosted Paritok
`level` semantics remain unverified (no key). Every log row names its
`compressor` backend so fallback rows can never masquerade as GPU results.
