# Headroom — Project Story

## What inspired it

Every long agent session ends the same way: `compacting conversation…`, and the
constraint you gave at turn 3 is gone. Not paraphrased — gone. The agent then
confidently re-introduces the bug you told it about an hour ago.

The thing that bothered me wasn't that context gets compressed. It's *when*.
Compaction is a cliff: nothing happens, nothing happens, then a summarizer runs
over the whole history at once and you lose the beginning of the session in a
single step. And the alternative on offer — a fixed compression policy, "always
squeeze tool output at L1, history at L3" — spends the cost of compression on
every turn whether the window is under pressure or not.

Both are the same mistake in opposite directions: **the compression decision is
not connected to the actual state of the window.**

So: treat context like a resource with a load factor, and compress the way you'd
evict from a cache — gradually, cheapest thing first, and only once you're
actually running out.

## What it is

An OpenAI-compatible proxy. One `BASE_URL` change and any agent gets it:

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8791/v1
```

Every message is classified on arrival (system / user / assistant / file read /
tool output / search) and **kept in original form forever**. Each turn the
controller measures occupancy

$$O \;=\; \frac{\sum_i t(s_i)}{W}, \qquad W = \texttt{HEADROOM\_WINDOW}\ (\text{default } 32\text{k})$$

and does the least it can get away with:

- *O* < *w*<sub>lo</sub> — change nothing. Most turns land here.
- *O* ≥ *w* ∈ {0.50, 0.70, 0.85} — re-plan the layout. Low-priority
  classes exhaust their whole compression ladder *L*₀ → *L*₃ *before* a
  higher-priority class loses a single byte. The system prompt, pinned
  constraints, and the last two turns stay byte-identical, unconditionally.

Two invariants do most of the work:

1. **Re-compress always from the original**, never from an already-compressed
   version — otherwise you get generation loss, and by turn 60 the summary of a
   summary of a summary says nothing.
2. **Between re-plans the rendered prefix is byte-stable**, so prompt caching
   behaves as if the proxy weren't there. A re-plan that changes levels is an
   *epoch* — a deliberate, counted cache miss. The 105-turn run needed exactly
   one.

## How I built it, and how I tried to break it

Logging came first, before any compression logic: a JSONL row per turn with
occupancy, per-segment level, token counts, and the name of the compressor
backend that produced each byte. The dashboard reads only from that log — it
can't show a number the log doesn't contain. That constraint turned out to be
the most useful decision in the project, because it made every later claim
checkable.

Then the benchmark, designed to be able to say *no*: one scripted 105-turn
debugging session, five facts planted mid-briefing in turns 1–3, forked probes
at turns 25/50/100, **exact-substring scoring — no LLM grader**. Three arms:

| Arm | Policy | Turns | Facts in context @25/50/100 | Model restated @25/50/100 | Avg tok/turn | Peak $O$ | Epochs |
|---|---|---|---|---|---|---|---|
| A | direct + compact-at-90% | 105 | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 5,647 | 88.6% | — |
| B | fixed policy (tool L1 / history L3) | 105 | 0/5 · 0/5 · 0/5 | 0/5 · 0/5 · 0/5 | 7,876 | 43.9% | — |
| C | **Headroom** | 105 | **5/5 · 5/5 · 5/5** | **2/5 · 3/5 · 4/5** | 16,464 | 79.6% | **1** |

Upstream is a real model (SleepyAI `laguna-s-2.1`), 326 live calls, 2 HTTP 502s
both recovered on retry.

The number I care about most isn't Headroom's 5/5. It's **Arm B's 43.9% peak
occupancy**: it destroyed all five facts while leaving more than half the window
unused. It compressed hard when nothing was pressing. That's the whole thesis in
one cell — a fixed policy pays the price of compression without the situation
that justifies it.

And Headroom does *not* win on tokens: ~2.9× Arm A, ~2.1× Arm B per turn.
Retention is bought with window, not for free. The table says so out loud.

## Challenges

**The compression backend went down mid-project.** Paritok's hosted GPU returns
HTTP 200 with `gpu_available: false` and your text echoed back unchanged — at
every level. A silent failure that looks like success is worse than an error,
because it quietly turns your system into a passthrough while the dashboard
still says "compressed." Headroom now detects the echo, falls back to its own
deterministic compressor, and stamps `compressor=local-fallback` on every
affected log row. No number in the results is attributed to Paritok.

**Verifying the thing I couldn't reach.** I pulled Paritok's open 4B model and
confirmed off it that `level` *is* honored — 32%/24%/19% output ratio for
L1/L2/L3 on a small input. Then I deliberately kept it out of the benchmark: on
realistic input it goes non-monotonic (L1 returns 100% of the input after 84 s;
L2 collapses to 9 tokens, losing every identifier), and it's my prompt template
against their weights, not their proxy. Reporting it as their performance would
have been the easy, wrong move.

**The scoring column I didn't want.** Exact-substring "is the fact still in
context" is a fair measure, but it measures what the model *could* see, not what
it does. So I added a strict second column: fork a live call at each probe, ask
the model to restate the constraints, grade its actual reply. Headroom is the
only arm that scores at all there — and it scores 2/5, 3/5, 4/5. Short of 5/5,
and published that way.

## What I learned

**Holding a fact in context does not mean the model uses it.** That gap — 5/5
present, 2/5 restated at turn 25 — is the honest ceiling on context engineering,
and it's invisible if you only measure retention.

**A benchmark that can't produce a bad number isn't a benchmark.** The
pre-registered facts, exact-substring scoring, and log-only dashboard existed
specifically so I couldn't tune my way to a nice result. The value of Arm B in
this project is that it's a *baseline that loses for a legible reason* — 0/5 at
43.9% occupancy — rather than an arm I built to lose.

**"Compress adaptively" is easy; "compress adaptively without destroying prompt
caching" is the actual problem.** Naive adaptivity rewrites the prefix every
turn and torches cache hits, converting a retention win into a
latency-and-cost loss. Byte-stable prefixes between counted epochs is the
design, and epoch count is a first-class metric for that reason.
