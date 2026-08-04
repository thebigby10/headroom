"""The occupancy controller.

Per request:  measure occupancy -> under low watermark? change nothing ->
crossed a watermark upward? re-plan the whole layout (one epoch) ->
only segments whose level changed get re-compressed, always from the original.

Also implements the two baseline arms so the benchmark compares like with like:
  stock    — Paritok's fixed policy: tool results L1, history L3, always
  compact  — no compression; at 90% occupancy summarize everything but the tail
"""

import hashlib
from dataclasses import dataclass, field

from . import log, tokens
from .segments import Segment, Store

WATERMARKS = [0.50, 0.70, 0.85]
REPLAN_MARGIN = 0.20  # re-plan digs well below the crossed watermark: each epoch
                      # buys many turns of slack, keeping epochs (= cache misses) rare
PIN_LAST_MESSAGES = 4  # last 2 exchanges + current turn stay untouched


@dataclass
class Session:
    id: str
    arm: str  # adaptive | stock | compact
    window: int
    store: Store = field(default_factory=Store)
    turn: int = 0
    epoch: int = 0       # counts re-plans (each is a deliberate cache miss)
    wm_level: int = 0    # highest watermark crossed so far
    levels: dict = field(default_factory=dict)  # segment_id -> level
    prev_rendered: list = field(default_factory=list)
    dead: bool = False


def _occupancy(segs: list[Segment], levels: dict, query: str) -> int:
    return sum(s.rep(levels.get(s.id, "L0"), query)[1] for s in segs)


def _positional_pinned(segs: list[Segment]) -> set:
    return {s.id for s in segs[-PIN_LAST_MESSAGES:]}


def _replan(segs, levels, pinned_ids, window, target_ratio, query):
    """Escalate lowest-priority classes FIRST and fully — a tool output reaches L3
    before any user turn loses a byte. Within a priority group: one ladder step
    per round, oldest segments first, stopping the moment we're under target."""
    eligible = sorted((s for s in segs if not s.pinned and s.id not in pinned_ids),
                      key=lambda s: (s.priority, s.arrival_turn))
    changed = set()
    by_prio: dict[int, list] = {}
    for s in eligible:
        by_prio.setdefault(s.priority, []).append(s)
    for prio in sorted(by_prio):
        group = by_prio[prio]
        while _occupancy(segs, levels, query) > target_ratio * window:
            bumped = False
            for s in group:
                cur = levels.get(s.id, "L0")
                i = s.ladder.index(cur) if cur in s.ladder else 0
                if i + 1 < len(s.ladder):
                    levels[s.id] = s.ladder[i + 1]
                    changed.add(s.id)
                    bumped = True
                    if _occupancy(segs, levels, query) <= target_ratio * window:
                        return changed
            if not bumped:
                break  # group exhausted; move to the next priority up
    return changed


def _stock_levels(segs: list[Segment]) -> dict:
    """Stock Paritok: current-turn tool results L1, all history L3, always."""
    levels = {}
    n = len(segs)
    for i, s in enumerate(segs):
        if s.pinned:
            continue
        if i >= n - 2:
            levels[s.id] = "L1" if s.cls == "tool_output" else "L0"
        else:
            levels[s.id] = "L3"
    return levels


def _compact(segs, levels, window, query):
    """Arm A: what agent tools do today — summarize-at-90%, facts flatten away."""
    if _occupancy(segs, levels, query) <= 0.90 * window:
        return segs
    keep_head = [s for s in segs if s.cls == "system"]
    tail = segs[-6:]
    dropped = [s for s in segs if s not in keep_head and s not in tail]
    if not dropped:
        return segs
    lines = [f"[Conversation compacted: {len(dropped)} earlier messages summarized]"]
    for s in dropped[-8:]:
        first = s.original.strip().splitlines()[0][:80] if s.original.strip() else ""
        lines.append(f"- {s.role}: {first}")
    summary = Segment("compact-" + hashlib.sha256("\n".join(lines).encode()).hexdigest()[:8],
                      "system", "system", 9, ["L0"], True, "\n".join(lines), segs[-1].arrival_turn)
    return keep_head + [summary] + tail


def handle(sess: Session, messages: list[dict], query: str = "") -> list[dict]:
    """Returns the outgoing (possibly compressed) message list, and logs everything."""
    sess.turn += 1
    segs = sess.store.ingest(messages, sess.turn)
    pinned_ids = _positional_pinned(segs)

    if sess.arm == "adaptive" and sess.wm_level:
        # under pressure, new arrivals adopt their class's prevailing level.
        # They render at the tail (and recent ones are positionally pinned), so
        # this never rewrites the prefix — it is not an epoch.
        prevailing: dict[str, str] = {}
        for s in segs:
            lvl = sess.levels.get(s.id)
            if lvl in s.ladder:
                best = prevailing.get(s.cls, "L0")
                if s.ladder.index(lvl) > s.ladder.index(best):
                    prevailing[s.cls] = lvl
        for s in segs:
            if (s.arrival_turn == sess.turn and not s.pinned
                    and s.id not in sess.levels and s.cls in prevailing):
                sess.levels[s.id] = prevailing[s.cls]
    was_changed: set = set()

    if sess.arm == "stock":
        new = _stock_levels(segs)
        was_changed = {k for k, v in new.items() if sess.levels.get(k, "L0") != v}
        sess.levels = new
    elif sess.arm == "adaptive":
        occ = _occupancy(segs, sess.levels, query)
        crossed = sum(1 for w in WATERMARKS if occ > w * sess.window)
        # re-plan on crossing a new watermark, and again whenever growth pushes
        # occupancy back above the top watermark
        if crossed > sess.wm_level or occ > WATERMARKS[-1] * sess.window:
            sess.wm_level = max(sess.wm_level, crossed)
            target = WATERMARKS[max(crossed, 1) - 1] - REPLAN_MARGIN
            was_changed = _replan(segs, sess.levels, pinned_ids, sess.window, target, query)
            if was_changed:  # an epoch = an actual layout change = the real cache miss
                sess.epoch += 1
    # compact: no per-segment levels

    out_segs = segs
    if sess.arm == "compact":
        out_segs = _compact(segs, sess.levels, sess.window, query)

    rendered, sent_total = [], 0
    for s in out_segs:
        level = "L0" if (s.pinned or s.id in pinned_ids) else sess.levels.get(s.id, "L0")
        text, ntok, backend = s.rep(level, query)
        rendered.append({"role": "user" if s.role in ("tool", "function") else s.role,
                         "content": text})
        sent_total += ntok
        log.write({
            "kind": "segment", "session": sess.id, "arm": sess.arm, "turn": sess.turn,
            "epoch": sess.epoch, "segment_id": s.id, "class": s.cls,
            "priority": s.priority, "assigned_level": level,
            "original_tokens": s.original_tokens, "sent_tokens": ntok,
            "was_recompressed": s.id in was_changed, "compressor": backend,
            "token_counter": tokens.COUNTER,
        })

    # prefix stability vs previous POST = cache-hit estimate
    stable = 0
    for prev, cur in zip(sess.prev_rendered, rendered):
        if prev != cur:
            break
        stable += tokens.count(cur["content"])
    sess.prev_rendered = rendered

    if sent_total > sess.window:
        sess.dead = True

    log.write({
        "kind": "request", "session": sess.id, "arm": sess.arm, "turn": sess.turn,
        "epoch": sess.epoch, "sent_tokens": sent_total, "window": sess.window,
        "occupancy_pct": round(100 * sent_total / sess.window, 1),
        "cache_stable_prefix_tokens": stable, "dead": sess.dead,
        "token_counter": tokens.COUNTER,
    })
    return rendered
