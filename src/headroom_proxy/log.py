"""The log is the backbone: one JSONL row per segment per upstream POST, plus one
request row with totals. If a number can't be read out of this log, it doesn't
count as a result. Dashboard and results tables read from here and nowhere else."""

import json
import os
import threading
import time

LOG_PATH = os.environ.get("HEADROOM_LOG", "logs/headroom.jsonl")
_lock = threading.Lock()

SEGMENT_FIELDS = [
    "ts", "kind", "session", "arm", "turn", "epoch", "segment_id", "class",
    "priority", "assigned_level", "original_tokens", "sent_tokens",
    "was_recompressed", "compressor", "token_counter",
]


def write(row: dict) -> None:
    row = {"ts": round(time.time(), 3), **row}
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with _lock, open(LOG_PATH, "a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def read_all(path: str = None) -> list[dict]:
    path = path or LOG_PATH
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]
