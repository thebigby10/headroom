# Step 4 report — The dashboard (H10–14)

Status: **all three views built**, in the plan's priority order, and verified by
rendering (screenshot in `docs/dashboard.png`).

## What was built (`dashboard/index.html`, single file, no dependencies)

1. **Live session view** — stacked occupancy bar by segment class with a turn
   scrubber, occupancy/epoch/window stat row, persistent fact-retention chips
   (✓/✗ with labels, never color alone), and the occupancy curve with the three
   watermarks, epoch markers, and probe positions.
2. **Three-arm comparison** — turns survived, facts at 25/50/100, avg
   tokens/turn, and epoch count for A, B, C side by side.
3. **Segment inspector** — click any segment in the bar: original vs sent text
   at its assigned level, tokens, class, priority, arrival turn, and which
   compressor backend produced it.

## The non-negotiable, honored

The page computes **nothing** of its own: every view fetches `/api/log` (the
benchmark's JSONL rows), `/api/summary` (written by the benchmark run), and
`/api/segment/{id}` (the persisted segment store). A judge can trace any number
on screen to a log row. The page banner says exactly that.

## Design notes

- Palette is the dataviz reference instance; the class→hue mapping was
  **validated with the palette checker against the adjacencies the stacked bar
  can actually produce** (tool→user→assistant cycle): all checks pass in light
  and dark. The light-mode contrast WARN is relieved by the segment table view
  and tooltips, per the relief rule. Assistant slivers render neutral gray
  ("Other"-style) — they are tiny structural filler; identity comes from
  legend, tooltip, and table.
- Sub-pixel segments drop their 2px separator so the bar's total width stays
  honest and the free-space region is real (was a bug: 316 × min-width+margin
  inflated the bar past 100% and squeezed out "free").
- Hover layer everywhere: per-segment tooltips on the bar, crosshair tooltip on
  the occupancy curve. Dark and light themes both styled; `data-theme` toggle
  respected.

## Verification

Served with `HEADROOM_LOG=logs/benchmark.jsonl uvicorn headroom_proxy.app:app`,
all endpoints returned live data (105 request rows, 316 segments at turn 105,
inspector round-trip OK), and the page was screenshot-checked headless for
label collisions and layout — one collision (70% watermark label vs data line)
found and fixed by moving watermark labels into a dedicated right margin.
