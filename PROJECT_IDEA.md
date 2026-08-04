# Headroom — Project Idea

**Form:** OpenAI-compatible proxy + live session dashboard
**Built on:** Paritok (hosted 4B compression model, free GPU)
**Target:** Build with Paritok — 1st place + Social Blitz + Most Valuable Feedback

---

## 1. One-line pitch

**Your agent stops forgetting what you asked for.**

Headroom keeps an agent's context window from filling up, so long sessions never hit the compaction cliff — the moment your tool says "compacting conversation…" and summarizes away the original bug description and the constraint you gave at turn 3.

## 2. How it's used

Point any OpenAI-compatible agent at Headroom with a single `BASE_URL` change. No code rewrite, no SDK, no framework buy-in. From then on:

- Headroom watches how full the context window is, turn by turn.
- While there's room, it barely touches anything.
- As pressure builds, it compresses the oldest, least important segments through Paritok — lightly at first, harder only as needed.
- The system prompt, the current task, and anything the user pins stay untouched at full fidelity, always.

## 3. The problem: everyone measures the wrong thing

Every project in the hackathon gallery measures **money** — tokens saved, cost avoided, percentage reduction. Paritok's own pitch is the same: 74% fewer input tokens, a live cost dashboard.

Money is real, but it isn't what breaks a developer's day. **The window is.**

The failure everyone has actually experienced: forty turns into a debugging session, a hundred tool calls, several large file reads — the agent hits its context limit. The tool summarizes the conversation to make room, keeping the recent back-and-forth while flattening everything early. Gone: the exact file path you said not to touch, the numeric constraint you specified once, the original description of what was wrong. The agent continues, confidently, slightly wrong, and you find out twenty turns later.

Why this failure is the right target:

1. **It's binary and visible.** The session either survives or it doesn't. Nobody needs to trust your arithmetic the way they must with "we saved 41% of tokens."
2. **It's felt, not calculated.** Users notice it immediately; they only notice token counts if you show them a chart.
3. **Nobody in the gallery is working on it.** Ten submissions, all optimizing cost. Zero measuring session survival.

## 4. The mechanism: occupancy-targeted compression

Stock Paritok already compresses hard — but on a **fixed policy**. Per Pin-On-Expand's reading of `server.py`, tool results take the default L1 and history is hardcoded to L3. The level dial exists, is wired to the model, and **nothing ever chooses between values**. Turn 3 gets crushed to L3 just as hard when the window is 20% full as when it's 95% full. That's spending fidelity you didn't need to spend.

Headroom's per-turn control loop:

```
Every turn:
  │
  ├─ Step 1: MEASURE OCCUPANCY                (free, instant)
  │    How full is the window right now, broken
  │    down by segment class?
  │
  ├─ Step 2: IS THERE PRESSURE?               (the decision)
  │    Under the low watermark → change nothing.
  │    Most turns land here. Compression that
  │    doesn't need to happen, doesn't.
  │
  ├─ Step 3: RE-PLAN THE LAYOUT               (only at epoch boundaries)
  │    Crossed a watermark? Re-assign compression
  │    levels across all segments — oldest and
  │    lowest-priority escalate first. Pinned
  │    content never moves.
  │
  └─ Step 4: EXECUTE VIA PARITOK              (hosted GPU)
       Only segments whose assigned level changed
       get re-compressed, from the ORIGINAL text,
       never from an already-compressed version.
```

### The claim, stated precisely

> Occupancy-targeted compression reaches the same session length as uniform aggressive compression, while retaining materially more of the early session — because it doesn't spend fidelity it doesn't need to spend.

Note what this claim is *not*: it is not "we save more tokens than stock Paritok." Stock already compresses hard; on raw token count it may well win. The trade is explicit — **same survival, better fidelity** — a defensible, testable, honest claim.

## 5. "Isn't this just Paritok's proxy with extra steps?"

The first question any judge will ask, answered directly:

- **Paritok's proxy** compresses on a fixed policy: tool results L1, history L3, always, regardless of whether the window is nearly empty or nearly full. It has no notion of a budget.
- **Headroom** treats the window as a budget to be spent deliberately. It compresses *as little as it can get away with*, escalating only under pressure, and never touches pinned content.

That's a claim, not proof — so the benchmark's Arm B is **stock Paritok** under identical conditions, and the project is arranged so that if Headroom doesn't clearly beat it on fidelity at equal survival, that is discovered at hour 6, not at submission time.

## 6. The defensibility detail: epochs

**The strongest objection to the whole idea:** compressing history invalidates prompt caching. Caching is prefix-based, so rewriting an old message busts the cache for everything after it. Recompress every turn and you may lose more to cache misses than you gain.

**Headroom's answer:** re-plan in *epochs*, not per turn. The compression layout is recomputed only when occupancy crosses a watermark — roughly four or five times across a hundred-turn session. Between epoch boundaries the prefix is byte-stable and caching behaves exactly as it would without a proxy. Instead of an uncounted cache miss every turn, you take a deliberate, **counted** cache miss at each of four or five boundaries — and that cost goes in the results table.

Turning the strongest objection into a named design feature is what separated the best gallery submission from the rest.

## 7. Segment classification and priority

Everything in the context is classified once, on arrival, and assigned a priority. Priority decides escalation order under pressure.

| Class | Priority | Escalation behaviour |
|---|---|---|
| System prompt | **Pinned** | Never compressed, ever |
| Pinned constraints (user-marked) | **Pinned** | Never compressed, ever |
| Last 2 turns | **Pinned** | Never compressed — recency is load-bearing |
| Current user turn | **Pinned** | Never compressed |
| Tool schemas | High | L1 only under heavy pressure |
| Recent assistant reasoning | High | L0 → L1 |
| Older user turns | Medium | L0 → L1 → L2 |
| File reads | Medium | L1 → L2 |
| Tool output / command output | Low | L1 → L2 → L3 first |
| Old search results | Low | L2 → L3 first |

**The invariant that matters:** re-compression always runs against the **original stored text**, never against an already-compressed version. Headroom keeps the original of every segment. This costs memory and buys correctness — content compressed at L1 and later escalated to L3 goes original → L3, not L1 → L3.

## 8. Deliverables

| # | Piece | What it is | Priority |
|---|---|---|---|
| 1 | **Proxy** | OpenAI-compatible `/v1/chat/completions` with the occupancy controller | **Must ship** |
| 2 | **Benchmark** | Three arms, planted facts, probes at turns 25/50/100 | **Must ship** |
| 3 | **Session dashboard** | Live occupancy view + fidelity readout + three-arm comparison | **Must ship** |
| 4 | **Upstream issue** | The level-selector proposal, with measurements attached | Free, do it |

## 9. The dashboard — making the invisible visible

The controller is invisible; nobody can *see* a compression level being chosen. The dashboard makes it visible and is worth more time than anything else in the UI.

```
TURN 63 · epoch 3 of a 128k window

[████████ system ][███ tools ][█████████ history ][██████ tool output ][    free    ]
 pinned  4.2k      pinned 6.1k  L1  31.4k          L3  22.8k            27.1k

Occupancy 79%  ·  watermark 85%  ·  next epoch in ~9 turns

Facts from turn 1 still intact:  5 / 5   ✓ path  ✓ limit  ✓ prohibition  ✓ version  ✓ code
```

Watching the bar fill, an epoch fire, and the fact counter *hold at 5/5 while the baseline arm drops to 2/5* is the entire demo. It is visceral in a way a percentage never is.

## 10. Deliberately out of scope

Accounts, persistence across restarts, streaming responses, multi-user, model routing, cost estimation in dollars, theming. This is a proxy, a benchmark, and one dashboard.

## 11. Honest limitations (stated before a judge finds them)

- Prompt caching already discounts stable prefixes heavily. Headroom's argument is about window *capacity*, not purely cost — and capacity is not something caching helps with at all.
- One benchmark task is one task. The result is a demonstration, not a general law.
- Retention is measured on five planted facts, not on overall answer quality.
- Epoch boundaries cost real cache misses; the count is in the table.
- If Paritok's stock defaults happen to suit your workload, a controller buys you less.
