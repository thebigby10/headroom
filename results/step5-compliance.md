# Step 5 report — Checkpoint 2: submission compliance (H14–16)

Status: everything automatable is **done**; the remaining items need the user's
accounts and are listed with exact actions.

## Done in the repo

- [x] **Apache 2.0** — full license text in `LICENSE`; `pyproject.toml` set.
- [x] **Paritok credited with link** in README (required line), plus the badge.
- [x] **`examples/`** — `demo.html` (self-contained dashboard with the real run
  inlined — judges evaluate without executing anything) and
  `run-2026-08-04/` (gzipped raw JSONL log, summary JSON, checkpoint verdict).
- [x] **Setup instructions that work from a clean clone** — README quickstart
  (uv venv → run benchmark → serve dashboard) mirrors exactly the commands
  used to build this; tests pass (`tests/test_headroom.py`, ALL PASS).
- [x] **Instant demo, no account** — artifact URL (below) pre-loaded with the
  recorded session; also `open examples/demo.html` offline.
- [x] Drafts ready: `docs/upstream-issue.md` (Most Valuable Feedback),
  `docs/social-post.md` (#BuiltWithParitok), `docs/video-script.md` (<3:00).

Demo artifact (starts private — share from the artifact page):
https://claude.ai/code/artifact/0d700201-71e8-4dd1-8f99-0fee2e1fb6d3

## Needs the user (accounts / outward-facing — not done on purpose)

1. **Create the public GitHub repo and push** (`git remote add … && git push`).
   Then set the About section to show the Apache-2.0 license.
2. **Public demo hosting** if a non-artifact URL is wanted: any static host
   serves `examples/demo.html` as-is (Netlify/Pages drag-and-drop works —
   it's one file).
3. **Paritok account**: sign up, put the account email in the Devpost form,
   and set `PARITOK_API_KEY` + rerun `benchmark/run.py` to upgrade the run
   from the disclosed local fallback to hosted GPU numbers.
4. **File the GitHub issue** from `docs/upstream-issue.md` on the Paritok repo
   with tag `hackathon-feedback` (outward-facing — user's call).
5. **Record the video** from `docs/video-script.md`; post from
   `docs/social-post.md` with `#BuiltWithParitok`.
6. Devpost submission by **3:00pm SGT, Aug 5**.
