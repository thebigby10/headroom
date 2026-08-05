# LinkedIn post

---

My baseline deleted all five of the user's constraints while **56% of the
context window sat completely empty.**

That one number is why I built Headroom.

Every long agent session ends the same way: `compacting conversation…`, and the
thing you said at turn 3 — the do-not-touch directory, the 400ms budget, the
pinned version — is gone. Not paraphrased. Gone. Then the agent confidently
reintroduces the bug you warned it about an hour ago.

The usual fixes are the same mistake in opposite directions. Compaction is a
cliff: nothing, nothing, nothing, then you lose the start of the session in one
step. A fixed compression policy is the other extreme: it squeezes on every
turn whether the window is under pressure or not.

Both share one flaw — **the compression decision isn't connected to the actual
state of the window.**

So Headroom treats context like a cache: measure occupancy, and evict
gradually, cheapest thing first, only once you're actually running out. It's an
OpenAI-compatible proxy, so adopting it is one line:

export OPENAI_BASE_URL=http://127.0.0.1:8791/v1

No SDK change. No rewrite. Below the watermark it does literally nothing.

I benchmarked it the way you benchmark something you want to be *able* to
disprove: one scripted 105-turn debugging session, five facts planted in turns
1–3 and written down before any code ran, forked probes at turns 25/50/100,
exact-substring scoring — no LLM grader marking its own homework.

Facts surviving at turns 25 / 50 / 100:

→ Compaction: 0/5 · 0/5 · 0/5
→ Fixed-level policy: 0/5 · 0/5 · 0/5 (peak occupancy: 43.9%)
→ **Headroom: 5/5 · 5/5 · 5/5** (peak 79.6%, exactly one cache-invalidating epoch)

Three things I'll say out loud, because a demo that only reports its wins isn't
evidence:

**1. Headroom costs more tokens.** ~2.9× the compaction baseline per turn.
Retention is bought with window, not for free. That column is in the table.

**2. Holding a fact in context ≠ the model using it.** So I added a stricter
column: fork a live call, ask the model to restate the constraints, grade its
actual reply. Headroom is the only arm that scores at all there — and it scores
2/5, 3/5, 4/5. Short of perfect. Published that way.

**3. The most interesting bug wasn't mine.** The compression API accepts a
`level` parameter, L0 through L3, and ignores it — same input returned 302,
289, 302, 302 characters. My controller assumed escalating always reclaims
space, so it escalated everything, reclaimed nothing, and overflowed the
window; two of three arms died mid-run. The fix is a floor: when every ladder
is spent, evict and leave a tombstone, so the model is *told* something is
missing instead of having its history quietly rewritten. Filed upstream.

The lesson I'm taking with me: "compress adaptively" is easy. "Compress
adaptively without destroying prompt caching" is the actual problem — and a
silent failure that returns HTTP 200 is worse than an outage, because your
dashboard keeps saying everything is fine.

Live demo (recorded run, no setup, no API key):
https://thebigby10.github.io/headroom/

Code, logs, and every number traceable to a log row:
https://github.com/thebigby10/headroom

Apache-2.0. Built with Paritok compression, SleepyAI as the task model.

#BuiltWithParitok #AI #LLM #ContextEngineering #AIAgents #Hackathon #OpenSource #MachineLearning
