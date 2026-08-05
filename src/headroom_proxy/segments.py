"""Segment store. One segment per message; the ORIGINAL text is kept forever and
every re-compression runs original -> level, never compressed -> compressed.
Representations are cached per level so unchanged epochs are byte-stable."""

import hashlib
from dataclasses import dataclass, field

from . import compressor, tokens

# class -> (priority, escalation ladder). Lower priority escalates first.
# Pinned classes never appear here; they are flagged, not laddered.
CLASS_TABLE = {
    "system":      (9, ["L0"]),
    "pinned":      (9, ["L0"]),
    "tool_schema": (4, ["L0", "L1"]),
    "assistant":   (4, ["L0", "L1"]),
    "user":        (3, ["L0", "L1", "L2"]),
    "file_read":   (2, ["L0", "L1", "L2"]),
    "search":      (1, ["L0", "L2", "L3"]),
    "tool_output": (1, ["L0", "L1", "L2", "L3"]),
}


def classify(role: str, content: str) -> str:
    if role == "system":
        return "system"
    if "[PINNED]" in content[:200]:
        return "pinned"
    if role in ("tool", "function"):
        return "tool_output"
    head = content[:80].lower()
    if head.startswith(("tool output:", "command output:", "$ ")):
        return "tool_output"
    if head.startswith(("search results", "grep results")):
        return "search"
    if head.startswith(("file:", "file contents", "```path=")):
        return "file_read"
    return "assistant" if role == "assistant" else "user"


@dataclass
class Segment:
    id: str
    role: str
    cls: str
    priority: int
    ladder: list
    pinned: bool
    original: str
    arrival_turn: int
    reps: dict = field(default_factory=dict)  # level -> (text, tokens, backend)

    def rep(self, level: str, query: str = ""):
        if level not in self.reps:
            if level == "EVICT":
                # ponytail: tombstone, not deletion — keeps message order intact and
                # tells the model a segment is gone instead of silently rewriting history
                text, backend = (
                    f"[{self.cls} from turn {self.arrival_turn} dropped to fit the context window]",
                    "evicted",
                )
            else:
                text, backend = compressor.compress(self.original, level, query, self.cls)
            self.reps[level] = (text, tokens.count(text), backend)
        return self.reps[level]

    @property
    def original_tokens(self) -> int:
        return self.rep("L0")[1]


class Store:
    def __init__(self):
        self.by_id: dict[str, Segment] = {}

    def ingest(self, messages: list[dict], turn: int) -> list[Segment]:
        out = []
        for m in messages:
            content = m.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            sid = hashlib.sha256(f"{m['role']}\x00{content}".encode()).hexdigest()[:16]
            seg = self.by_id.get(sid)
            if seg is None:
                cls = classify(m["role"], content)
                prio, ladder = CLASS_TABLE[cls]
                seg = Segment(sid, m["role"], cls, prio, ladder,
                              cls in ("system", "pinned"), content, turn)
                self.by_id[sid] = seg
            out.append(seg)
        return out
