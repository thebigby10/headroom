# AGENTS.md

OpenAI-compatible proxy + benchmark rig that compresses an agent's context window
by occupancy instead of fixed policy. Non-streaming by design. The project's real
purpose is a measured three-arm A/B claim in `results/checkpoint1.md`; the codebase
is the harness for that experiment.

## Setup & env

- Venv is Python 3.12 at `.venv` (`.venv/` is gitignored).
- Install deps: `uv pip install -p .venv/bin/python fastapi uvicorn httpx tiktoken`
  (`pyproject.toml` lists only fastapi/uvicorn/httpx; `tiktoken` is optional but
  recommended — without it token counting silently degrades to a chars/4 estimate,
  disclosed per log row).
- `.env` (gitignored) holds `PARITOK_API_KEY`, `SLEEPY_AI_API_KEY`,
  `HEADROOM_MODEL`. It is loaded on `import headroom_proxy` via `os.environ.setdefault`.
  Never print or commit these.
- No pytest / ruff / mypy / formatter / CI exist. There is no lint/typecheck gate.

## Key commands (all offline-with-mock by default)

- Tests (milestone checks, plain script — no pytest): `.venv/bin/python tests/test_headroom.py`
  - Sets a temp `HEADROOM_LOG` and pops real API keys after import, so it ALWAYS
    runs against the mock and never burns credits. Mirror that pattern in new tests.
- Benchmark: `.venv/bin/python benchmark/run.py` (~2s offline, 3 arms, writes `logs/`).
  With `SLEEPY_AI_API_KEY` set it makes ~326 live upstream calls — budget for it.
- Build the self-contained demo: `.venv/bin/python scripts/make_demo.py`
- Checkpoint probes (need real keys / ollama): `scripts/checkpoint0_probe.py`,
  `scripts/paritok_local_probe.py`
- Serve dashboard: 
  ```
  HEADROOM_LOG=logs/benchmark.jsonl PYTHONPATH=src .venv/bin/python -m uvicorn headroom_proxy.app:app --port 8791
  ```

## Layout

- `src/headroom_proxy/` — src layout; `pyproject.toml` packages `headroom_proxy` only.
  Scripts (`benchmark/`, `scripts/`) insert `..src` into `sys.path` themselves; only
  the `uvicorn` run needs `PYTHONPATH=src`.
- `src/headroom_proxy/*`: `app.py` FastAPI proxy (POST `/v1/chat/completions` +
  `/api/*` + dashboard) · `controller.py` occupancy re-planner · `segments.py`
  segment store · `compressor.py` compression backends · `upstream.py` task model ·
  `log.py` JSONL log · `tokens.py` counting.
- `dashboard/index.html` is a single file that reads ONLY from the log API (or
  `window.HEADROOM_DATA` inlined by `make_demo.py`). `docs/`, `results/`,
  `examples/` hold the writeup and recorded runs; `EXECUTION_PLAN.md`, the
  `*.md` specs, and `docs/dashboard.png` are submission artifacts.

## Hard invariants (do not break)

- The **log is the backbone**: "if a number can't be read out of the log it doesn't
  count as a result." Dashboard and all result tables read from `logs/benchmark.jsonl`
  (`log.read_all`), never re-derived. Preserve this when adding metrics.
- A segment's ORIGINAL text is kept forever; **every re-compression runs
  original→level, never compressed→compressed** (`segments.py:55`).
- Compression tier precedence in `compressor.compress`: hosted Paritok → local
  ollama 4B → deterministic local fallback. Trust hosted only when response is
  2xx AND `gpu_available` AND non-empty. The hosted Paritok GPU is currently DOWN
  (returns 200 + passthrough), so runs stamp `compressor=local-fallback`. Do not
  attribute benchmark numbers to Paritok.
- Adaptive arm pins the system prompt and the last 4 messages byte-identical;
  occupancy watermarks 50/70/85%; each layout change = one `epoch` (a counted,
  deliberate cache miss).
- Arms addressed via `X-Headroom-Arm: adaptive|stock|compact|off`; sessions via
  `X-Headroom-Session`.

## Conventions

- `classify` in `segments.py` guesses message class off the content prefix; pinned
  content is flagged by literal `"[PINNED]"` in the first 200 chars — tests rely on it.
- Every log row names its `compressor` backend and `token_counter`; keep both honest.
- `logs/` is gitignored; recorded runs live under `examples/run-<date>/` and are
  committed. Working docs live in `docs/`; build/verdict notes in `results/`.