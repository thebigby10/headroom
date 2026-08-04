"""Deterministic 100+ turn debugging-session transcript with five planted facts.

THE FACTS AND PROBE QUESTIONS BELOW WERE WRITTEN BEFORE ANY ARM RAN (plan §4.6).
Facts sit mid-paragraph inside a long turn-1 briefing on purpose: a fact on its
own short line survives any compressor trivially and would rig the comparison.
Scoring is exact substring match — reproducible or not, no LLM grader.
"""

import random

FACTS = {
    "path": "src/adapters/legacy_parser.py",
    "limit": "response must stay under 400ms",
    "prohibition": "do not modify anything under vendor/",
    "version": "psycopg 2.9.3",
    "error_code": "E_CONN_4471",
}

PROBE_QUESTION = (
    "Before we continue: restate, exactly, (1) the file path where the failure "
    "surfaces, (2) the latency constraint, (3) what you were told not to modify, "
    "(4) the pinned database driver version, (5) the error code."
)

_BRIEFING = f"""We have a production incident and I need a careful, methodical debugging session.
Context on the system first. The service is a payments ingestion pipeline that has been
running since 2019. It consumes events from three upstream partners, normalizes them,
and writes settlement records. Most of the code is modern, but there is a legacy
normalization layer we have been meaning to retire for two years.
Traffic roughly tripled after the Q2 launch, and the on-call rotation has been seeing
intermittent failures during the nightly reconciliation window.
The failure we care about surfaces inside {FACTS['path']}, in the retry wrapper around
the connection pool acquisition, and under load the {FACTS['error_code']} error appears in
the logs a few seconds before the worker recycles itself.
A few hard constraints for this whole session. Because the SLA with the largest partner
is contractual, the {FACTS['limit']} at p95 for the ingest endpoint, measured at the load
balancer, not the app. Also, licensing on the bundled connectors means you must
absolutely {FACTS['prohibition']} — everything in there is vendored third-party code we
redistribute under a no-modification clause.
On dependencies: we are pinned to {FACTS['version']} because 2.9.4 changed the
default isolation behaviour under our pooler and broke reconciliation once already;
do not suggest an upgrade as a fix.
The database layer talks to Postgres 14 through pgbouncer in transaction mode. The
workers are gevent-based, 8 per pod, 12 pods. Connection storms have happened before.
Start by getting oriented in the repository, then reproduce the failure with the
nightly reconciliation fixture, then work hypotheses one at a time. Keep notes as
you go and tell me what you find before changing anything."""


def _file_read(rng, t):
    name = f"src/pipeline/stage_{t % 17}.py"
    lines = [f"FILE: {name}"]
    for i in range(rng.randint(80, 140)):
        lines.append(f"    def handle_{i}(self, batch):  # normalize partner {i % 3} records")
        lines.append(f"        cursor.execute(SQL_{i}, batch.rows[{i}:{i + rng.randint(2, 9)}])")
    return "\n".join(lines)


def _test_output(rng, t):
    lines = [f"TOOL OUTPUT: pytest tests/reconciliation -k nightly_{t}"]
    for i in range(rng.randint(50, 90)):
        status = "PASSED" if rng.random() > 0.2 else "FAILED"
        lines.append(f"tests/reconciliation/test_nightly.py::test_case_{t}_{i} {status} [{i}%]")
    lines.append(f"=== {rng.randint(1, 6)} failed, {rng.randint(40, 80)} passed in {rng.randint(4, 30)}.{t % 10}s ===")
    return "\n".join(lines)


def _grep(rng, t):
    lines = [f"Search results for 'pool_acquire' round {t}:"]
    for i in range(rng.randint(20, 40)):
        lines.append(f"src/db/pool_{i % 7}.py:{rng.randint(10, 400)}: conn = pool_acquire(timeout={rng.choice([5, 10, 30])})")
    return "\n".join(lines)


def build_transcript(n_turns: int = 105):
    """Yields (turn_number, messages_so_far). Message list grows like a real agent
    session: user asks, assistant replies, tool output lands."""
    rng = random.Random(0)
    msgs = [{"role": "system",
             "content": "You are a senior debugging agent working a production incident. "
                        "Follow the operator's constraints exactly for the entire session."}]
    tools = [_file_read, _test_output, _grep]
    for t in range(1, n_turns + 1):
        if t == 1:
            msgs.append({"role": "user", "content": _BRIEFING})
        elif t == 2:
            msgs.append({"role": "user", "content":
                         "Also, before you start: reconfirm you understand the constraints I just "
                         "gave, then list the directories at repo root and open the entrypoint."})
        elif t == 3:
            msgs.append({"role": "user", "content":
                         "Good. One more piece of context: the incident channel says the worker "
                         "recycling started around 02:14 UTC. Now begin with the fixture run."})
        else:
            msgs.append({"role": "user", "content": rng.choice([
                f"Keep going — what does stage {t % 17} look like?",
                "Run the nightly fixture again and compare failures.",
                "Search for where the pool timeout is configured.",
                f"Hypothesis {t}: could this be pgbouncer transaction-mode pinning? Check.",
                "Read the next module in the trace and summarize what it does.",
            ])})
        msgs.append({"role": "assistant", "content":
                     f"Turn {t}: proceeding. " + rng.choice([
                         "Reading the module and tracing the acquisition path.",
                         "Running the fixture; watching for the error code in output.",
                         "Comparing failure sets against the previous run.",
                         "That narrows it — checking the pool configuration next.",
                     ])})
        msgs.append({"role": "user", "content": tools[t % 3](rng, t)})
        yield t, msgs
