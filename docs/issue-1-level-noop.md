# `level` is accepted and silently discarded on the hosted path

**Tag:** `hackathon-feedback`
**Endpoint:** `POST https://www.paritok.com/api/compress`
**Measured:** 2026-08-05, valid key, `gpu_available: true`

## Summary

The hosted API accepts a `level` parameter, returns 200, and produces the same
output regardless of which level was requested. The parameter is validated by
the schema and then has no observable effect. Meanwhile the open 4B weights
*do* honor `level`, so hosted and self-hosted disagree about what the same
request means.

## Reproduction

Same content, same headers, only `level` varying:

```bash
for L in L0 L1 L2 L3; do
  curl -s -X POST https://www.paritok.com/api/compress \
    -H "Authorization: Bearer $PARITOK_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"<~5000 chars of natural prose>\",
         \"query\": \"why does the connection fail?\",
         \"kind\": \"tool_output\", \"level\": \"$L\"}" \
    | python -c "import json,sys; b=json.load(sys.stdin); \
        print('$L', b['gpu_available'], len(b['compressed']))"
done
```

Result:

| level | HTTP | `gpu_available` | output chars |
|---|---|---|---|
| L0 | 200 | true | 302 |
| L1 | 200 | true | 289 |
| L2 | 200 | true | 302 |
| L3 | 200 | true | 302 |

All four land at ~6% of the original. **L0 and L3 are indistinguishable.**

For contrast, the same ladder against the open 4B weights self-hosted:

| level | output as % of original |
|---|---|
| L1 | 32% |
| L2 | 24% |
| L3 | 19% |

Monotonic, and clearly a graded ladder. The hosted path is not.

## Impact

This is the expensive kind of bug because it is silent. A client cannot detect
it from the response — 200, `gpu_available: true`, plausible output — so it
builds policy on a dial that does not turn.

Ours did. Headroom escalates lowest-priority segments up a per-class ladder
(`L0 → L1 → L2 → L3`) when context occupancy crosses a watermark, on the
assumption that compressing harder reclaims space. Against the hosted path it
escalated every eligible segment to the top of its ladder, reclaimed nothing,
and overflowed a 32k window. **Two of three benchmark arms died mid-session** —
peak occupancy 100.3% and 101.0%, at turns 48 and 58 of a 105-turn run.

We diagnosed it only because every log row records which backend produced it.
A client without that instrumentation would see sessions dying and blame its
own controller.

The hosted/self-hosted divergence compounds it: code tuned against the weights
behaves differently against the API, with nothing in either response indicating
which semantics are in force.

## What we'd ask for

1. **Honor `level` on the hosted path**, matching the self-hosted ladder — or
2. **Reject it with a 400** as unsupported. A discarded parameter is strictly
   worse than an absent one; had it 400'd, we would have designed around it in
   an hour instead of losing a benchmark run to it.
3. Either way, **document the per-level contract** — what L1 vs L3 should
   target — and state whether hosted and self-hosted are intended to agree.
