"""Compression backends, tried in order; every result says which one produced it.

1. Hosted Paritok — only when the response *proves* compression happened
   (2xx AND gpu_available AND non-empty). Never assumed: a missing key returns
   401 + verbatim passthrough, and a *valid* key against a downed GPU returns
   200 + verbatim passthrough. Both were observed live (results/checkpoint0.md).
2. Local Paritok 4B via ollama — the self-host path the hosted service itself
   points at when its GPU is unreachable. Opt-in via PARITOK_OLLAMA_MODEL.
3. Deterministic local fallback with distinct L1/L2/L3 behaviour.
"""

import os
import re

import httpx

PARITOK_ENDPOINT = os.environ.get("PARITOK_ENDPOINT", "https://www.paritok.com/api/compress")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
# opt-in: the hosted 200-but-uncompressed response names this exact model
PARITOK_OLLAMA_MODEL = os.environ.get("PARITOK_OLLAMA_MODEL")

LEVELS = ["L0", "L1", "L2", "L3"]

_LEVEL_BRIEF = {
    "L1": "Remove redundant whitespace, filler and boilerplate. Keep all content.",
    "L2": "Keep only the parts relevant to the query; drop the rest.",
    "L3": "Compress hard into a terse summary of a few lines.",
}


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


def compress_ollama(text: str, level: str, query: str = "") -> str | None:
    """Paritok's own 4B model, self-hosted. Returns None on any failure so the
    caller falls through — a compressor that silently returns nothing is worse
    than one that admits it's unavailable."""
    # /api/chat, not /api/generate: this is a Qwen3 with ChatML stop tokens, and
    # raw-prompted it autocompletes the input instead of compressing it (it
    # cheerfully continued 60 lines of log). The chat endpoint applies the
    # template and it behaves. keep_alive avoids re-paying the 3.8GB cold load.
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": PARITOK_OLLAMA_MODEL, "stream": False, "keep_alive": "30m",
                  "messages": [
                      {"role": "system", "content":
                       "You compress context for an LLM. Output only the rewritten "
                       "content, nothing else. Preserve every identifier, file path, "
                       "version number, error code and quoted string EXACTLY as written."},
                      {"role": "user", "content":
                       f"{_LEVEL_BRIEF[level]}\nQUERY: {query or '(none)'}\n\nCONTENT:\n{text}"},
                  ],
                  "options": {"temperature": 0}},
            timeout=300,
        )
        if r.status_code >= 300:
            return None
        return (r.json().get("message", {}).get("content") or "").strip() or None
    except (httpx.HTTPError, ValueError):
        return None


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
            pass  # fall through
    if PARITOK_OLLAMA_MODEL:
        out = compress_ollama(text, level, query)
        if out:
            return out, "paritok-local-4b"
    return compress_local(text, level, query), "local-fallback"
