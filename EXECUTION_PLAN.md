# Headroom — Execution Plan

**Structure:** three phases, three hard checkpoints. **Each checkpoint is a stop condition, not a suggestion.**

```
H0–1    Checkpoint 0: Do the two external dependencies actually work?
H1–6    Build proxy + controller
H6–10   Checkpoint 1: Does adaptive beat stock on fidelity?
H10–14  Dashboard
H14–16  Checkpoint 2: Deploy + repo compliance
H16–19  Video, issue, social post
```

**Start here — hour zero is Checkpoint 0.** Not the proxy, not the UI. Verify that `level` actually changes Paritok's output on the hosted path, and that SleepyAI reports `prompt_tokens`. Those two answers decide whether you build the project as designed or the pivot in §1.3. Finding out at hour zero costs an hour; finding out at hour eight costs the submission.

**First commit: the logging.**

---

## 1. Checkpoint 0 — Verification gate (H0–1)

**Do not write a single line of the controller until these are answered.** Both are external dependencies you don't control, and either can invalidate the design.

### 1.1 SleepyAI (task model)

- [ ] Does the response include a `usage` object with `prompt_tokens`? *(If no → count with tiktoken and state this openly in the writeup. Do not estimate silently.)*
- [ ] What is the maximum context length it accepts? *(That's your window size. If it's small, arms reach failure faster — actually good for the demo.)*
- [ ] Does it support prompt caching? *(If no → the epoch design still holds but the cache-miss column becomes N/A. Say so.)*
- [ ] What are the rate limits? *(You will run 100+ turn sessions three times. Budget for this now.)*

### 1.2 Paritok hosted GPU

- [ ] Does your API key work against `/api/compress`? *(Segpilot documented that the endpoint returns 200 for garbage and absent keys alike — a "working" response does not prove your key registers. Confirm usage attribution on the dashboard.)*
- [ ] Does `level` actually change the output? *(Segpilot reports the hosted GPU silently ignores it and accepts `level="BANANA"` with HTTP 200. **This is the single biggest risk in the project.** Test L0 vs L3 on identical input and diff the results.)*
- [ ] Typical latency per call, and can you run 10 in parallel?

### 1.3 Contingency: `level` is a no-op on the hosted path

Don't abandon the project — **pivot the mechanism**. Instead of varying level, vary *what you send*: pinned segments pass through untouched, low-priority segments get compressed, and escalation means "compress more segments" rather than "compress harder." Same claim, same benchmark, same dashboard. Rewrite the controller's escalation function and nothing else. This contingency is why Checkpoint 0 exists at hour zero rather than hour eight.

### 1.4 Sign-off

Every box above answered **in writing**, in `results/checkpoint0.md`, before H1.

---

## 2. H1–3 — Proxy skeleton and logging

**Build the logging first.** Every upstream POST writes one row — not a summary, not an aggregate:

```
turn · epoch · arm · segment_id · class · priority · assigned_level
     · original_tokens · sent_tokens · provider_prompt_tokens
     · latency_ms · was_recompressed · cache_hit_estimated
```

That log is the backbone of everything: the dashboard reads from it, the results table is computed from it, and every number in the writeup traces back to it. **If something can't be read out of this log, it doesn't get to count as a result.**

Then the passthrough: FastAPI, `POST /v1/chat/completions`, forward to SleepyAI, return the response unchanged. Non-streaming only — streaming is a time sink with no demo value here.

**Milestone:** an agent pointed at the proxy behaves exactly as if it weren't there, and every call is logged.

---

## 3. H3–6 — The controller

Four pieces, in this order:

1. **Segment store.** Every message decomposed into segments, each keeping the original text permanently, plus a content hash, arrival turn, class, and priority.
2. **Occupancy accounting.** Sum of currently-assigned token counts by class, against the window ceiling determined at Checkpoint 0.
3. **Level policy.** Given target occupancy and current usage, walk segments in (priority ascending, age descending) order and escalate until under budget. Pinned segments are skipped unconditionally.
4. **Epoch trigger.** Watermarks at 50% / 70% / 85%. Crossing one upward re-plans the layout; nothing else does.

**Milestone:** a synthetic 40-turn transcript runs through the controller, occupancy stays under the ceiling, epochs fire at expected points, and pinned content is byte-identical at the end.

---

## 4. Checkpoint 1 — Does adaptive actually beat stock? (H6–10)

**The only question that matters at this stage:**

> At equal session survival, does Headroom retain more of the early session than stock Paritok?

**Nothing else gets built until this is answered.** Not the dashboard, not the deploy, not the video.

### 4.1 The three arms

| Arm | What it does | Point of it |
|---|---|---|
| A | Direct to provider, summarize-at-90% compaction | The **real** baseline — what every agent tool does today |
| B | **Stock Paritok proxy**, default levels | **The real competitor** |
| C | **Headroom** — occupancy-targeted adaptive | What's being tested |

Beating A proves little; A is known-weak and exists to show the category is real. **Arm B decides the project.** It must be a fair, unmodified stock configuration — a hobbled B would be worse than no comparison at all.

### 4.2 The benchmark task

One long agent task that genuinely runs 100+ turns. A multi-bug debugging session over a mid-size repo works well — read files, run tests, hypothesize, read more files. Chained unrelated bugs generate the context drift you need.

**Plant five checkable facts in turns 1–3:**

| # | Fact type | Example |
|---|---|---|
| 1 | Exact file path | `src/adapters/legacy_parser.py` |
| 2 | Numeric constraint | "response must stay under 400ms" |
| 3 | Prohibition | "do not modify anything under `vendor/`" |
| 4 | Version string | "we're pinned to psycopg 2.9.3" |
| 5 | Error code | "the failure surfaces as `E_CONN_4471`" |

Chosen because they're **exactly reproducible or not** — no judgment call, no LLM grader, no argument. That property makes this benchmark credible where fuzzier retention metrics aren't.

### 4.3 Probing protocol

At turns 25, 50, and 100, take the context **as it currently stands** and issue a *forked* call asking the agent to restate the five constraints. Score exact match.

**Fork, don't append.** The probe must not enter the real session history, or you've contaminated the very thing you're measuring. Same context, separate call, discard the result after scoring.

### 4.4 What gets measured (per arm)

Turns survived before failure or ceiling · occupancy curve over time · **fact retention at 25/50/100** · provider `prompt_tokens` per turn · cumulative tokens · epoch count · estimated cache-miss cost at epoch boundaries.

### 4.5 Pass criteria and decision

- **🟢 Strong pass** — Headroom matches or exceeds Arm B on turns survived **and** retains at least 2 more facts at turn 50. → The claim holds in full. Build the dashboard.
- **🟡 Pass, narrower claim** — equal survival with 1 more fact retained, or clearly longer survival at equal retention. → Still a real result. Narrow the headline to exactly what you measured — *"same session length, better early-context fidelity"* — and move on.
- **🔴 Fail** — no meaningful difference from stock on either axis. → The controller has become "Paritok with extra steps." **Pivot the same hour.** The rig, logging, and planted-fact benchmark all carry over: re-point the identical harness at *pinning* instead of levels — never compress segments the model has previously had to re-read. Narrower claim, still novel, still measurable with everything already built.

### 4.6 Sign-off

- [ ] All three arms run from one command
- [ ] Planted facts and probe questions were written **before** any arm ran
- [ ] Arm B is stock and unmodified
- [ ] `results/checkpoint1.md` contains the table and a clear verdict
- [ ] Token figures come from provider `usage`, not estimates (or the estimate is disclosed)
- [ ] Decision recorded: **Strong pass / Pass / Fail** → next step

**The dashboard does not get started until every box is checked.**

---

## 5. H10–14 — The dashboard

Three views, in priority order. If time runs short, build 1 and 2 and skip 3.

1. **Live session view.** Stacked occupancy bar by segment class, turn counter, epoch markers, and the persistent fact-retention readout. This is the demo.
2. **Three-arm comparison.** Retention at 25/50/100 for A, B, C side by side, with Arm A visibly dying first.
3. **Segment inspector.** Click any segment to see original vs compressed, with its assigned level and the epoch it was set at.

**Non-negotiable:** the dashboard reads from the same log the benchmark uses. Not a parallel calculation, not hardcoded numbers. If a judge can't trace a number on screen back to a log row, it isn't proof.

---

## 6. Checkpoint 2 — Submission compliance (H14–16)

Pass/fail requirements from the rules page. Missing one can cost the prize regardless of quality.

- [ ] Public repo, **Apache 2.0 license file, visible in the GitHub About section**
- [ ] README credits Paritok with a link: `Built with [Paritok](https://github.com/Paritok-official/paritok-4b-v1)`
- [ ] Paritok badge at top of README (optional, cheap, do it)
- [ ] **Paritok account email** in the submission form — how judges verify hosted-GPU usage
- [ ] Publicly accessible demo URL, no account required to try it
- [ ] `examples/` folder with saved runs, so judges can evaluate without executing anything
- [ ] Full setup instructions that actually work from a clean clone
- [ ] Deployed and confirmed working from a browser you've never used

---

## 7. H16–19 — Video, issue, social post

### 7.1 Video (under 3 minutes — hard limit)

- **0:00–0:25** — Show the failure first. Arm A, mid-session, compaction fires, the agent forgets the prohibition and edits `vendor/`. Lead with the problem, not the architecture.
- **0:25–1:00** — What Headroom does. `BASE_URL` swap, one line. Occupancy bar filling.
- **1:00–2:00** — Epoch fires. Fact counter holds at 5/5 while the baseline drops. This is the money shot; give it room.
- **2:00–2:40** — The three-arm table. Say the honest limitation out loud.
- **2:40–3:00** — Repo, license, Paritok credit.

### 7.2 GitHub issue (Most Valuable Feedback track)

Tag it `hackathon-feedback`. The proposal: *the `level` dial is fully implemented and wired to the model, but nothing ever selects between values — tool results always take L1, history is hardcoded L3.* Attach measurements showing what a selector buys. Include whatever Checkpoint 0 found about `level` behaviour on the hosted path, with a reproducer. A feature proposal grounded in data is precisely what the bonus criterion asks for.

### 7.3 Social post (Social Blitz track)

Tag `#BuiltWithParitok`. Lead with the GIF of the fact counter holding while the baseline drops. Hook: *"Your agent hit its context limit and quietly forgot what you asked for. I measured how much it forgot — and fixed it."*

---

## 8. Cut list, if time runs short (in order)

1. Segment inspector view
2. Three-arm comparison view (fold the numbers into the README table instead)
3. Arm A entirely — B vs C is the comparison that matters; A is nice framing
4. Probes at turn 100 (25 and 50 carry the story)
5. Epoch cache-miss accounting (mention it as designed-for, measured-later)

**Never cut:** the logging, the planted-fact benchmark, Arm B, and the live occupancy view. Those four *are* the proof. Everything else is presentation.

---

## 9. Risk register

| Risk | How bad | What to do about it |
|---|---|---|
| Hosted `level` is a no-op | **Fatal to the mechanism** | Checkpoint 0, hour zero. Pivot to "what gets compressed" rather than "how hard" |
| SleepyAI won't take long contexts | High | Arms can't reach failure. Use a smaller synthetic window ceiling and say so |
| Rate limits during 3× 100-turn runs | High | Cache aggressively; record sessions once and replay offline for reruns |
| Headroom ties with stock Paritok | High | Checkpoint 1 catches it at H10, with a defined pivot |
| Compressing history busts caching | Medium | Epoch design; count the boundary cost honestly |
| Dashboard eats the whole day | Medium | It's H10–14 and capped. Benchmark first, always |
| Building broadly, finishing nothing | High | This is what the checkpoints are for |

---

## 10. Results table shape (do not pre-fill)

```
                    Turns    Facts@25   Facts@50   Facts@100   Tokens/turn   Epochs
A  direct+compact     ~48       5/5        2/5         —           high         —
B  stock Paritok     100+       4/5        2/5        1/5          low          —
C  Headroom          100+       5/5        5/5        4/5          low-mid      4
```

Illustrative shape only — do not pre-fill these numbers, and do not write the headline before the run. Whatever comes out, report it.

---

## 11. Final submission checklist (by 3:00pm SGT, Aug 5)

- [ ] Deployed demo, no account needed, pre-loaded with a recorded session so it works instantly
- [ ] Public repo, Apache 2.0 in About, Paritok credited with a link
- [ ] `examples/` with saved runs and the raw log
- [ ] README: the one-line idea, the three-arm results table, honest limitations, setup instructions
- [ ] Video under 3 minutes, public on YouTube
- [ ] Devpost submission with Paritok account email filled in
- [ ] GitHub issue tagged `hackathon-feedback`
- [ ] Social post tagged `#BuiltWithParitok`
