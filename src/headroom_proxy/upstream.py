"""Upstream task model. SleepyAI when SLEEPY_AI_API_KEY is set, else a
deterministic mock so the whole rig runs offline. The mock's answers are never
scored — fact retention is scored on the CONTEXT SENT UPSTREAM, not on prose."""

import hashlib
import os
import time

import httpx

from . import tokens

BASE_URL = os.environ.get("SLEEPY_AI_BASE_URL", "https://www.sleepyai.org/api/v1")


def name() -> str:
    return "sleepyai" if os.environ.get("SLEEPY_AI_API_KEY") else "mock"


def chat(messages: list[dict], model: str = "gpt-4", max_tokens: int = 512) -> dict:
    key = os.environ.get("SLEEPY_AI_API_KEY")
    if key:
        r = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "stream": False,
                  "max_tokens": max_tokens},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()

    # deterministic mock: echoes a stable reply, reports honest token counts
    prompt_tokens = sum(tokens.count(m.get("content") or "") for m in messages)
    seed = hashlib.sha256(repr([m.get("content", "")[:64] for m in messages]).encode()).hexdigest()[:8]
    text = f"[mock-{seed}] Acknowledged turn; continuing the investigation."
    return {
        "id": f"mock-{seed}", "object": "chat.completion", "created": int(time.time()),
        "model": "mock-offline",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": tokens.count(text),
                  "total_tokens": prompt_tokens + tokens.count(text),
                  "estimated": True, "token_counter": tokens.COUNTER},
    }
