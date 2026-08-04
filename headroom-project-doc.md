# Headroom — Project Doc

**App:** Headroom · **Form:** OpenAI-compatible proxy + live session dashboard
**Time budget:** ~19 working hours · **Built on:** Paritok (hosted 4B, free GPU)
**Target:** Build with Paritok — 1st place + Social Blitz + Most Valuable Feedback
**Deadline:** Aug 5, 2026 @ 12:00am PDT ≈ **3:00pm Singapore time**

---

## Part 1 — The Idea

### 1.1 What it is, in plain terms

**Headroom keeps your agent's context window from filling up, so long sessions don't quietly lose the thing you asked for.**

You point any OpenAI-compatible agent at it with a `BASE_URL` change. No code rewrite, no SDK, no framework buy-in. From then on:

- Headroom watches how full the context window is, turn by turn.
- While there's room, it barely touches anything.
- As pressure builds, it compresses the oldest, least important segments through Paritok — lightly at first, harder only as needed.
- The system prompt, the current task, and anything you pinned stay untouched at full fidelity, always.

The result is a session that keeps going without ever hitting the compaction cliff — the moment where your tool says "compacting conversation…" and summarizes your history away, taking the original bug description and the constraint you gave at turn 3 with it.

**One line: your agent stops forgetting what you asked for.**

### 1.2 The problem underneath: everyone is measuring the wrong thing

Every project in this hackathon's gallery measures **money** — tokens saved, cost avoided, percentage reduction. Paritok's own pitch is the same: 74% fewer input tokens, a live cost dashboard.

Money is real, but it isn't what breaks a developer's day. **The window is.**

Here's the failure everyone has actually experienced. You're deep into a debugging session. Forty turns in, a hundred tool calls, several large file reads. The agent hits its context limit. Your tool summarizes the conversation to make room — and the summary keeps the recent back-and-forth while flattening everything early. Gone: the exact file path you said not to touch. The numeric constraint you specified once. The original description of what was actually wrong.

The agent then continues, confidently, slightly wrong, and you don't find out for another twenty turns.

That failure has three properties worth noticing:

1. **It's binary and visible.** The session either survives or it doesn't. Unlike "we saved 41% of tokens," nobody needs to trust your arithmetic.
2. **It's felt, not calculated.** Users notice it immediately. They only notice token counts if you show them a chart.
3. **Nobody in the gallery is working on it.** Ten submissions, all optimizing cost. Zero measuring session survival.

### 1.3 The fix: target an occupancy budget, don't compress uniformly

Stock Paritok already compresses hard. Per Pin-On-Expand's reading of `server.py`, tool results take the default L1 and history is hardcoded to L3 — **the level dial exists, is wired to the model, and nothing ever chooses between values.**

That means turn 3 gets crushed to L3 just as hard when the window is 20% full as when it's 95% full. That's spending fidelity you didn't need to spend.

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

**The claim, stated precisely:**

> Occupancy-targeted compression reaches the same session length as uniform aggressive compression, while retaining materially more of the early session — because it doesn't spend fidelity it doesn't need to spend.

Note what this claim is *not*. It is not "we save more tokens than stock Paritok." Stock already compresses hard; on raw token count it may well win. The trade being made is explicit: **same survival, better fidelity.** That's a defensible, testable, honest claim, and it's the right one to make.

### 1.4 "Isn't this just Paritok's proxy with extra steps?"

This is the first question any judge will ask, and it deserves a direct answer rather than a dodge.

- **Paritok's proxy** compresses on a fixed policy. Tool results L1, history L3, always, regardless of whether the window is nearly empty or nearly full. It has no notion of a budget.
- **Headroom** treats the window as a budget to be spent deliberately. It compresses *as little as it can get away with*, escalating only under pressure, and it never touches pinned content.

That's a claim, not proof — so **Arm B of the benchmark is stock Paritok**, run under identical conditions, and the whole project is arranged so that if Headroom doesn't clearly beat it on fidelity at equal survival, that is discovered at hour 6 rather than at submission time.

### 1.5 The design detail that makes it defensible: epochs

**The strongest objection to this whole idea:** compressing history invalidates prompt caching. Caching is prefix-based, so rewriting an old message busts the cache for everything after it. Recompress every turn and you may lose more to cache misses than you gain.

**Headroom's answer:** re-plan in *epochs*, not per turn.

The compression layout is recomputed only when occupancy crosses a watermark — roughly four or five times across a hundred-turn session. Between epoch boundaries the prefix is byte-stable and caching behaves exactly as it would without a proxy.

So instead of an uncounted cache miss on every single turn, you take a deliberate, **counted** cache miss at each of four or five epoch boundaries — and you put that cost in the results table.

Turning the strongest objection into a named design feature is what separated the best submission in the gallery from the rest. Do the same here.

### 1.6 Segment classification and priority

Everything in the context gets classified once, on arrival, and assigned a priority. Priority decides escalation order under pressure.

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

### 1.7 What actually gets built

| # | Piece | What it is | Priority |
|---|---|---|---|
| 1 | **Proxy** | OpenAI-compatible `/v1/chat/completions` with the occupancy controller | **Must ship** |
| 2 | **Benchmark** | Three arms, planted facts, probes at turns 25/50/100 | **Must ship** |
| 3 | **Session dashboard** | Live occupancy view + fidelity readout + three-arm comparison | **Must ship** |
| 4 | **Upstream issue** | The level-selector proposal, with measurements attached | Free, do it |

### 1.8 What the dashboard looks like

The controller is invisible — nobody can *see* a compression level being chosen. The dashboard is what makes it visible, and it is worth more time than anything else in the UI.

```
TURN 63 · epoch 3 of a 128k window

[████████ system ][███ tools ][█████████ history ][██████ tool output ][    free    ]
 pinned  4.2k      pinned 6.1k  L1  31.4k          L3  22.8k            27.1k

Occupancy 79%  ·  watermark 85%  ·  next epoch in ~9 turns

Facts from turn 1 still intact:  5 / 5   ✓ path  ✓ limit  ✓ prohibition  ✓ version  ✓ code
```

Watching the bar fill, watching an epoch fire, and watching the fact counter *hold at 5/5 while the baseline arm drops to 2/5* is the entire demo. It is visceral in a way a percentage never is.

**Deliberately not in scope:** accounts, persistence across restarts, streaming responses, multi-user, model routing, cost estimation in dollars, theming. This is a proxy, a benchmark, and one dashboard.

---

## Part 2 — Execution Plan

Three phases, three hard checkpoints. **Each checkpoint is a stop condition, not a suggestion.**

```
H0–1    Checkpoint 0: Do the two external dependencies actually work?
H1–6    Build proxy + controller
H6–10   Checkpoint 1: Does adaptive beat stock on fidelity?
H10–14  Dashboard
H14–16  Checkpoint 2: Deploy + repo compliance
H16–19  Video, issue, social post
```

### 2.1 Checkpoint 0 — Verification gate (H0–1)

**Do not write a single line of the controller until these are answered.** Both are external dependencies you don't control, and either one can invalidate the design.

**SleepyAI (your task model):**

- [ ] Does the response include a `usage` object with `prompt_tokens`? *(If no → count with tiktoken and state this openly in the writeup. Do not estimate silently.)*
- [ ] What is the maximum context length it accepts? *(This is your window size. If it's small, arms reach failure faster — which is actually good for the demo.)*
- [ ] Does it support prompt caching? *(If no → the epoch design still holds but the cache-miss column in your results table becomes N/A. Say so.)*
- [ ] What are the rate limits? *(You will run 100+ turn sessions three times. Budget for this now.)*

**Paritok hosted GPU:**

- [ ] Does your API key work against `/api/compress`? *(Segpilot documented that the endpoint returns 200 for garbage and absent keys alike — so a "working" response does not prove your key is registering. Check the dashboard to confirm usage is being attributed to your account.)*
- [ ] Does `level` actually change the output? *(Segpilot reports the hosted GPU silently ignores it and accepts `level="BANANA"` with HTTP 200. **This is the single biggest risk in the project.** Test L0 vs L3 on identical input and diff the results.)*
- [ ] Typical latency per call, and can you run 10 in parallel?

**If `level` genuinely doesn't work on the hosted path:** don't abandon the project — pivot the mechanism. Instead of varying level, vary *what you send*: pinned segments pass through untouched, low-priority segments get compressed, and escalation means "compress more segments" rather than "compress harder." Same claim, same benchmark, same dashboard. Rewrite the controller's escalation function and nothing else. **This contingency is why Checkpoint 0 exists at hour zero rather than hour eight.**

**Sign-off:** every box above answered in writing, in `results/checkpoint0.md`, before H1.

---

### 2.2 H1–3 — Proxy skeleton and logging

**Build the logging first.** Every upstream POST writes one row. Not a summary, not an aggregate — one row per call, containing:

```
turn · epoch · arm · segment_id · class · priority · assigned_level
     · original_tokens · sent_tokens · provider_prompt_tokens
     · latency_ms · was_recompressed · cache_hit_estimated
```

That log is the backbone of everything: the dashboard reads from it, the results table is computed from it, and every number in the writeup traces back to it. **If something can't be read out of this log, it doesn't get to count as a result.**

Then the passthrough: FastAPI, `POST /v1/chat/completions`, forward to SleepyAI, return the response unchanged. Non-streaming only — streaming is a time sink with no demo value here.

**Milestone:** an agent pointed at the proxy behaves exactly as if it weren't there, and every call is logged.

### 2.3 H3–6 — The controller

Four pieces, in this order:

1. **Segment store.** Every message decomposed into segments, each with the original text kept permanently, plus a content hash, arrival turn, class, and priority.
2. **Occupancy accounting.** Sum of currently-assigned token counts by class, against the window ceiling from Checkpoint 0.
3. **Level policy.** Given target occupancy and current usage, walk segments in (priority ascending, age descending) order and escalate until under budget. Pinned segments are skipped unconditionally.
4. **Epoch trigger.** Watermarks at 50% / 70% / 85%. Crossing one upward re-plans the layout; nothing else does.

**Milestone:** a synthetic 40-turn transcript runs through the controller, occupancy stays under the ceiling, epochs fire at expected points, and pinned content is byte-identical at the end.

---

### 2.4 Checkpoint 1 — Does adaptive actually beat stock? (H6–10)

**The only question that matters at this stage:**

> At equal session survival, does Headroom retain more of the early session than stock Paritok?

**Nothing else gets built until this is answered.** Not the dashboard, not the deploy, not the video.

**The three arms:**

| Arm | What it does | Point of it |
|---|---|---|
| A | Direct to provider, summarize-at-90% compaction | The **real** baseline — what every agent tool does today |
| B | **Stock Paritok proxy**, default levels | **The real competitor** |
| C | **Headroom** — occupancy-targeted adaptive | What's being tested |

Beating A proves little; A is known-weak and exists to show the category is real. **Arm B is the one that decides the project.** It must be a fair, unmodified stock configuration. A hobbled B would be worse than no comparison at all.

#### 2.4.1 The benchmark task

One long agent task that genuinely runs 100+ turns. A multi-bug debugging session over a mid-size repo works well — read files, run tests, hypothesize, read more files. Chained unrelated bugs generate the context drift you need.

**Plant five checkable facts in turns 1–3:**

| # | Fact type | Example |
|---|---|---|
| 1 | Exact file path | `src/adapters/legacy_parser.py` |
| 2 | Numeric constraint | "response must stay under 400ms" |
| 3 | Prohibition | "do not modify anything under `vendor/`" |
| 4 | Version string | "we're pinned to psycopg 2.9.3" |
| 5 | Error code | "the failure surfaces as `E_CONN_4471`" |

These are chosen because they're **exactly reproducible or not** — no judgment call, no LLM grader, no argument. That's the property that makes this benchmark credible where fuzzier retention metrics aren't.

#### 2.4.2 How probing works

At turns 25, 50, and 100, take the context **as it currently stands** and issue a *forked* call asking the agent to restate the five constraints. Score exact match.

**Fork, don't append.** The probe must not enter the real session history, or you've contaminated the very thing you're measuring. Same context, separate call, discard the result after scoring.

#### 2.4.3 What gets measured

Per arm: turns survived before failure or ceiling, occupancy curve over time, **fact retention at turns 25/50/100**, provider `prompt_tokens` per turn, cumulative tokens, epoch count, and estimated cache-miss cost at epoch boundaries.

#### 2.4.4 What counts as a pass

**🟢 Strong pass** — Headroom matches or exceeds Arm B on turns survived **and** retains at least 2 more facts at turn 50.
→ The claim holds in full. Build the dashboard.

**🟡 Pass, narrower claim** — equal survival with 1 more fact retained, or clearly longer survival at equal retention.
→ Still a real result. Narrow the headline to exactly what you measured — *"same session length, better early-context fidelity"* — and move on.

**🔴 Fail** — no meaningful difference from stock on either axis.
→ The controller has become "Paritok with extra steps." **Pivot the same hour.** The rig, the logging, and the planted-fact benchmark all carry over: re-point the identical harness at *pinning* instead of levels — never compress segments the model has previously had to re-read — which is a narrower claim but still novel and still measurable with everything you've already built.

#### 2.4.5 Checkpoint 1 sign-off

- [ ] All three arms run from one command
- [ ] Planted facts and probe questions were written **before** any arm ran
- [ ] Arm B is stock and unmodified
- [ ] `results/checkpoint1.md` contains the table and a clear verdict
- [ ] Token figures come from provider `usage`, not estimates (or the estimate is disclosed)
- [ ] Decision recorded: **Strong pass / Pass / Fail** → next step

**The dashboard does not get started until every box is checked.**

---

### 2.5 H10–14 — The dashboard

Three views, in priority order. If time runs short, build 1 and 2 and skip 3.

1. **Live session view.** The stacked occupancy bar by segment class, turn counter, epoch markers, and the persistent fact-retention readout. This is the demo.
2. **Three-arm comparison.** Retention at 25/50/100 for A, B and C side by side, with Arm A visibly dying first.
3. **Segment inspector.** Click any segment to see original vs compressed, with its assigned level and the epoch it was set at.

**Non-negotiable:** the dashboard reads from the same log the benchmark uses. Not a parallel calculation, not hardcoded numbers. If a judge can't trace a number on screen back to a log row, it isn't proof.

---

### 2.6 Checkpoint 2 — Submission compliance (H14–16)

These are pass/fail requirements from the rules page. Missing one can cost the prize regardless of quality.

- [ ] Public repo, **Apache 2.0 license file, visible in the GitHub About section**
- [ ] README credits Paritok with a link: `Built with [Paritok](https://github.com/Paritok-official/paritok-4b-v1)`
- [ ] Paritok badge at top of README (optional, cheap, do it)
- [ ] **Paritok account email** in the submission form — this is how judges verify hosted-GPU usage
- [ ] Publicly accessible demo URL, no account required to try it
- [ ] `examples/` folder with saved runs, so judges can evaluate without executing anything
- [ ] Full setup instructions that actually work from a clean clone
- [ ] Deployed and confirmed working from a browser you've never used

---

### 2.7 H16–19 — Video, issue, social post

**Video (under 3 minutes, and this is a hard limit).** Structure:

- **0:00–0:25** — Show the failure first. Arm A, mid-session, compaction fires, the agent forgets the prohibition and edits `vendor/`. Lead with the problem, not the architecture.
- **0:25–1:00** — What Headroom does. `BASE_URL` swap, one line. Occupancy bar filling.
- **1:00–2:00** — Epoch fires. Fact counter holds at 5/5 while the baseline drops. This is the money shot; give it room.
- **2:00–2:40** — The three-arm table. Say the honest limitation out loud.
- **2:40–3:00** — Repo, license, Paritok credit.

**GitHub issue (Most Valuable Feedback track).** Tag it `hackathon-feedback`. The proposal: *the `level` dial is fully implemented and wired to the model, but nothing ever selects between values — tool results always take L1, history is hardcoded L3.* Attach your measurements showing what a selector buys. Include whatever you found at Checkpoint 0 about `level` behaviour on the hosted path, with a reproducer. This is a feature proposal grounded in data, which is precisely what the bonus criterion asks for.

**Social post (Social Blitz track).** Tag `#BuiltWithParitok`. Lead with the GIF of the fact counter holding while the baseline drops. Hook: *"Your agent hit its context limit and quietly forgot what you asked for. I measured how much it forgot — and fixed it."*

---

## Part 3 — Reference Material

### 3.1 What to cut, in order, if time runs short

1. Segment inspector view
2. Three-arm comparison view (fold the numbers into the README table instead)
3. Arm A entirely — B vs C is the comparison that matters; A is nice framing
4. Probes at turn 100 (25 and 50 carry the story)
5. Epoch cache-miss accounting (mention it as designed-for, measured-later)

**Never cut:** the logging, the planted-fact benchmark, Arm B, and the live occupancy view. Those four *are* the proof. Everything else is presentation.

### 3.2 Risks worth watching

| Risk | How bad | What to do about it |
|---|---|---|
| Hosted `level` is a no-op | **Fatal to the mechanism** | Checkpoint 0, hour zero. Pivot to "what gets compressed" rather than "how hard" |
| SleepyAI won't take long contexts | High | Arms can't reach failure. Use a smaller synthetic window ceiling and say so |
| Rate limits during 3× 100-turn runs | High | Cache aggressively; record sessions once and replay offline for reruns |
| Headroom ties with stock Paritok | High | Checkpoint 1 catches it at H10, with a defined pivot |
| Compressing history busts caching | Medium | Epoch design; count the boundary cost honestly |
| Dashboard eats the whole day | Medium | It's H10–14 and capped. Benchmark first, always |
| Building broadly, finishing nothing | High | This is what the checkpoints are for |

### 3.3 Honest limitations to state in the writeup

State these before a judge finds them. Every one of them makes the submission stronger, not weaker.

- Prompt caching already discounts stable prefixes heavily. Headroom's argument is about window *capacity*, not purely cost — and capacity is not something caching helps with at all.
- One benchmark task is one task. The result is a demonstration, not a general law.
- Retention is measured on five planted facts, not on overall answer quality.
- Epoch boundaries cost real cache misses; the count is in the table.
- If Paritok's stock defaults happen to suit your workload, a controller buys you less.

### 3.4 The results table you're aiming for

```
                    Turns    Facts@25   Facts@50   Facts@100   Tokens/turn   Epochs
A  direct+compact     ~48       5/5        2/5         —           high         —
B  stock Paritok     100+       4/5        2/5        1/5          low          —
C  Headroom          100+       5/5        5/5        4/5          low-mid      4
```

Illustrative shape only — do not pre-fill these numbers, and do not write the headline before the run. Whatever comes out, report it.

### 3.5 What must exist by 3:00pm SGT

- [ ] Deployed demo, no account needed, pre-loaded with a recorded session so it works instantly
- [ ] Public repo, Apache 2.0 in About, Paritok credited with a link
- [ ] `examples/` with saved runs and the raw log
- [ ] README: the one-line idea, the three-arm results table, honest limitations, setup instructions
- [ ] Video under 3 minutes, public on YouTube
- [ ] Devpost submission with Paritok account email filled in
- [ ] GitHub issue tagged `hackathon-feedback`
- [ ] Social post tagged `#BuiltWithParitok`

---

## Part 4 — Start Here

**Hour zero is Checkpoint 0.** Not the proxy, not the UI — verify that `level` actually changes Paritok's output on the hosted path, and that SleepyAI reports `prompt_tokens`.

Those two answers determine whether the project you build is the one described here or the pivot described in §2.1. Finding out at hour zero costs an hour. Finding out at hour eight costs the submission.

**First commit: the logging.**
