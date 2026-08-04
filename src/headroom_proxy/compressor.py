"""Compression backends.

Hosted Paritok when PARITOK_API_KEY is set AND the response proves compression
happened (gpu_available true, 2xx) — Checkpoint 0 showed a missing/bad key gets
401 + verbatim passthrough, so success is verified, never assumed.
Otherwise: deterministic local fallback with distinct L1/L2/L3 behaviour.
Every result says which backend produced it.
"""

import os
import re

import httpx

PARITOK_ENDPOINT = os.environ.get("PARITOK_ENDPOINT", "https://www.paritok.com/api/compress")

LEVELS = ["L0", "L1", "L2", "L3"]


def _l1(text: str) -> str:
    # collapse whitespace runs, drop blank lines
    lines = [re.sub(r"[ \t]+", " ", l.rstrip()) for l in text.splitlines()]
    return "\n".join(l for l in lines if l)


def _l2(text: str, query: str = "") -> str:
    lines = _l1(text).splitlines()
    if len(lines) <= 18:
        return "\n".join(lines)
    keywords = [w for w in re.findall(r"\w{4,}", query.lower())][:8]
    keep = set(range(10)) | set(range(len(lines) - 5, len(lines)))
    for i, l in enumerate(lines):
        if any(k in l.lower() for k in keywords):
            keep.add(i)
    out, skipped = [], 0
    for i, l in enumerate(lines):
        if i in keep:
            if skipped:
                out.append(f"… [elided {skipped} lines]")
                skipped = 0
            out.append(l)
        else:
            skipped += 1
    if skipped:
        out.append(f"… [elided {skipped} lines]")
    return "\n".join(out)


def _l3(text: str) -> str:
    lines = _l1(text).splitlines()
    if len(lines) <= 4:
        return "\n".join(lines)
    return "\n".join(lines[:2] + [f"… [L3: elided {len(lines) - 3} lines]", lines[-1]])


def compress_local(text: str, level: str, query: str = "") -> str:
    if level == "L0":
        return text
    if level == "L1":
        return _l1(text)
    if level == "L2":
        return _l2(text, query)
    return _l3(text)


def compress(text: str, level: str, query: str = "", kind: str = "history") -> tuple[str, str]:
    """Returns (compressed_text, backend_name)."""
    if level == "L0":
        return text, "none"
    key = os.environ.get("PARITOK_API_KEY")
    if key:
        try:
            r = httpx.post(
                PARITOK_ENDPOINT,
                headers={"Authorization": f"Bearer {key}"},
                json={"content": text, "query": query, "kind": kind, "level": level},
                timeout=30,
            )
            body = r.json()
            if r.status_code < 300 and body.get("gpu_available") and body.get("compressed"):
                return body["compressed"], "paritok-gpu"
        except (httpx.HTTPError, ValueError):
            pass  # fall through to local
    return compress_local(text, level, query), "local-fallback"
