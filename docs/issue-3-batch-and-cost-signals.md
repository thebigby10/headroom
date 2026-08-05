# Enhancement: batch endpoint, token counts, and rate-limit headers

**Tag:** `hackathon-feedback`
**Endpoint:** `POST https://www.paritok.com/api/compress`

## Summary

Context compression is inherently a fan-out over many segments, but the API is
one-segment-per-request with no cost signals in the response. Three additions
would each remove real friction; the first is the one that matters.

## 1. A batch endpoint

Our workload is one call per segment per re-plan. A single 3-arm, 105-turn
benchmark issues roughly **4,000 hosted compression calls** and takes ~30
minutes wall-clock, almost entirely network round-trips — each one is a
separate TLS request carrying a few KB.

This is not an unusual shape. Any context-management client compresses N
segments at a decision point, not one. A `POST /api/compress/batch` accepting
an array and returning results in order would collapse thousands of sequential
round-trips into tens.

```jsonc
// request
{"items": [{"content": "...", "query": "...", "kind": "tool_output", "level": "L2"},
           {"content": "...", "query": "...", "kind": "file_read",   "level": "L1"}]}
// response
{"results": [{"compressed": "...", "input_tokens": 1275, "output_tokens": 310},
             {"compressed": "...", "input_tokens": 840,  "output_tokens": 240}],
 "gpu_available": true}
```

## 2. Token counts in the response

The response returns compressed text and nothing about its size. For an
occupancy-driven controller, *the token count is the reason for the call* — we
compress specifically to get under a watermark. Today every client has to
re-tokenize the output locally to learn what it just bought, which means
guessing your tokenizer and being subtly wrong.

Returning `input_tokens` / `output_tokens` costs you nothing — you already have
them — and removes a whole class of client-side drift.

## 3. Rate-limit headers

No `X-RateLimit-*` or `Retry-After` on any response we saw. With a workload
that issues thousands of calls there is no way to back off intelligently; a
client either paces conservatively and wastes time, or hammers and hopes.
Standard headers would let clients self-regulate.

## Smaller gaps worth closing

- **No documented error taxonomy.** Which status codes are possible, and what
  each means. (See the companion issue on failures returning 200.)
- **No stated latency expectation.** We could not tell a slow call from a
  hanging one, so we picked a 30s timeout arbitrarily.
- **No hosted-vs-self-hosted parity statement.** We found the two disagree on
  `level` semantics; a sentence in the README would have saved a day.

## What worked, for balance

Genuinely worth keeping as-is:

- **The API surface is minimal and obvious** — one POST, four fields, bearer
  auth. We integrated in under an hour with no SDK and no client library.
- **Compression quality on real prose is good.** 1,796 chars → 431 while
  preserving the answer to the query. Measurably better than our deterministic
  fallback: on one hosted run the fixed-policy arm retained 3 of 5 planted
  facts at turn 25 where our local fallback retained 0 of 5. It is semantically
  smart — it just isn't aggressive enough to hold occupancy alone.
- **`gpu_available` exists.** Most services would have returned a bare 200. It
  is the only reason we detected an outage mid-benchmark. Promote it to a
  documented contract rather than removing it.
- **Open 4B weights.** Being able to self-host let us answer the `level`
  question independently when the hosted path was ambiguous. That is a real
  differentiator and it directly produced two of the three issues we filed.
