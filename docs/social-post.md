# Draft social post (tag: #BuiltWithParitok)

> Your agent hit its context limit and quietly forgot what you asked for.
> I measured how much it forgot — and fixed it.
>
> 40 turns into a debugging session, your tool says "compacting conversation…"
> and the constraint you gave at turn 3 is gone. You find out twenty turns
> later, when it edits the vendored code you told it not to touch.
>
> Headroom is a one-line BASE_URL swap that treats the context window as a
> budget: compress the old tool output hard, the file reads a little, the
> operator's actual words never — and only under pressure.
>
> Same 105-turn session, three ways:
> · today's compaction: 0/5 original constraints survive turn 25
> · fixed aggressive compression: 0/5 (it crushed them when the window was half-EMPTY)
> · occupancy-targeted: 5/5 at turn 100, with exactly one cache-busting re-plan
>
> [GIF: fact counter holding 5/5 while the baseline drops]
>
> Built on @Paritok's hosted compression for #BuiltWithParitok. Repo + live
> demo + every number traceable to a log row: <repo link>

Attach: screen recording of the dashboard scrubbing turns 1→105 on Arm C
(fact chips stay green) then switching to Arm B (chips go red by turn 25).
