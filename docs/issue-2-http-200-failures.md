# Failures are returned as HTTP 200 — including `compressed: ""`

**Tag:** `hackathon-feedback`
**Endpoint:** `POST https://www.paritok.com/api/compress`
**Measured:** 2026-08-04 and 2026-08-05, valid key

## Summary

Two distinct failure modes both return HTTP 200 with a well-formed body. A
client that trusts the status code cannot tell either of them from success, and
in both cases the natural thing to do — write `body["compressed"]` into your
context — silently destroys data.

## Variant A: GPU unavailable, valid key → 200 with content echoed back

Observed 2026-08-04 through 2026-08-05. **This one has since recovered**, so it
is not reproducible right now; we report it because the response envelope is a
standing design issue that will resurface at the next outage.

| request | HTTP | `gpu_available` | body |
|---|---|---|---|
| no key | **401** | false | content echoed |
| valid key | **200** | false | content echoed verbatim, identical at every level |

The unauthenticated case fails loudly and correctly. The authenticated case —
the one that matters — fails silently. `gpu_available: false` was the only
signal that anything was wrong.

## Variant B: GPU up, valid key → 200 with `compressed: ""`

Current and reproducible. Some inputs return an **empty string** — not a
missing field, not an error. All rows below measured within minutes of each
other, same headers, same body shape (`{content, query, kind, level}`):

| input | chars in | `compressed` out |
|---|---|---|
| real prose from our corpus | 1,796 | **431** ✅ |
| one sentence repeated 50× | 2,050 | `""` |
| one sentence repeated 150× | 6,150 | `""` |
| random words, 20-word vocabulary | 2,406 | `""` |
| random words, larger | 7,500 | `""` |

**Not a length threshold** — the 1,796-char input succeeds while the 7,500-char
one returns empty. It tracks whether the text reads as natural prose. Our guess
is the model emits an empty completion on degenerate input and that goes out
unwrapped.

Reproduction:

```bash
curl -s -X POST https://www.paritok.com/api/compress \
  -H "Authorization: Bearer $PARITOK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "The connection pool exhausts under load. [repeat 50x]",
       "query": "why does it fail?", "kind": "tool_output", "level": "L3"}'
# → 200 {"gpu_available": true, "compressed": ""}
```

## Impact

For a compression service this is the worst available failure shape: you cannot
distinguish **"compressed to nothing"** from **"we returned nothing."** Both are
`200` + `compressed: ""`.

A straightforward integration — check the status, take the field — writes an
empty string into the model's context and drops the segment. Nothing surfaces.
The agent just gets quieter and slightly wrong.

We survived both variants only because we never trusted the status code: we
gate on `gpu_available` and treat a falsy `compressed` as failure, falling back
to a local compressor and stamping the row so the log records which backend
produced every byte. In one completed live benchmark that guard fired on
**2,314 of 4,800 compression calls (48%)** — nearly all of them short
conversational turns, which are exactly the segments an unprotected client
would silently lose.

## What we'd ask for

1. **Return non-2xx when compression did not happen** — 503 for GPU
   unavailable, 422 for "input not compressible."
2. **Or add an explicit discriminator** — a `status` / `reason` field — so
   `compressed: ""` as a legitimate result is distinguishable from failure.
3. **Document `gpu_available` as the health contract.** It is currently the only
   reliable signal and it is not obviously load-bearing from the docs. It saved
   us twice; it should be stated, not discovered.
4. Never echo the input back as though it were output. Returning the original
   under a field named `compressed` is what makes the outage case silent.
