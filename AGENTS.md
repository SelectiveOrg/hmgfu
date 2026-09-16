# AGENTS.md — hmg-fu

Standalone prototype of the **HMG-Fu relational memory algorithm** (hex memory grid + Fu theory).
Not related to PriorAgent — do not cross-port code or assumptions.

**Before any work in this repo, read:**
1. `PROJECT_ID.md` — goal, scope, models, success criteria.
2. `ROADMAP.md` — living plan; every step is a checkbox ticked on disk with evidence.
3. `docs/THEORY.md` — the polished theory; all formulas implemented in `hmgfu/fu_math.py` trace back to it.

The 15 golden rules in `~/.Codex/AGENTS.md` are in force here.

## Runtime facts
- All models are local via Ollama: `gemma4:12b` (chat), `qwen2.5:1.5b-instruct` (sensitizer/dream nano), `gemma-cpu:latest` (nano-produced grader), `nomic-embed-text` (embeddings).
- Every tunable lives in `hmgfu/config.py`; env overrides are documented in README.md. No hidden flags.
- Tests in `tests/` run WITHOUT Ollama (fake embedder). Live checks: `scripts/smoke_live.py`.
- Run server: `python -m hmgfu.api` (serves API + `web/index.html`). CLI: `python -m hmgfu.cli`.
- Windows + Git Bash. venv at `.venv/` → `source .venv/Scripts/activate`.
