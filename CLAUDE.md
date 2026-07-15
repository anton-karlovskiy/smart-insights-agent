# CLAUDE.md

We're building the app described in @SPEC.md. Read that file for general architectural tasks or to double-check the exact pipeline contract, data schemas, tech stack, or repo layout.

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Whenever working with any third-party library or something similar, you MUST look up the official documentation to ensure that you're working with up-to-date information.
Use the DocsExplorer subagent for efficient documentation lookup.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: built, polishing

All seven pipeline stages are implemented and the tree matches `SPEC.md` §7: the `smart_insights/` package, the three committed artifacts, and a test suite that passes offline with no API key (`uv run pytest`). The build order in §8 is done, not pending.

What that changes for you:

- **The code is the source of truth for what exists; `SPEC.md` is the source of truth for what was intended.** Where they disagree, that is a finding to surface, not a licence to quietly "fix" either one.
- **`PROMPTS.md` is the annotated history of *why*** — read the relevant entry before changing a decision it records.
- **Work now is polish, not build-out.** Readability, tests, docs, and correctness against the existing contract. The simplicity rule below still governs: a new feature needs an explicit ask, and the pipeline contract, CLI commands, JSON artifact schemas, and prompt text are all stable surfaces — changing one is a deliberate act, not a side effect.

## What this is

A Python CLI (`python -m smart_insights`) that takes a messy dataset of OptinMonster customers' opt-in campaigns (`data/optinmonster_users.json`, one row per customer website), cleans/normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to produce one validated "next-best-action" recommendation per website. Target scope is a ~3–4h proof-of-concept — **prefer the simplest testable version of everything; no web framework, no database, no thin-segment fallbacks or other speculative features** (the user has repeatedly cut over-engineering — see `PROMPTS.md` §14).

## Core architecture (the non-obvious parts)

The whole design turns on one split: **deterministic Python owns every statistic and decision; the LLM is used only at two isolated points** and only to reshape prose it is given — never to author facts or numbers. Two ideas make the rest of the pipeline make sense:

1. **Preprocessing is a committed artifact, not a runtime step.** The only LLM-writing stage (stage 2, `preprocess.py`) is run once and its output committed to `data/enriched.json` + `data/segment_map.json`. Every other stage, and the *entire* test suite, reads those committed files and runs offline with no API key. This is why there is a separate `preprocess` CLI command distinct from `clean`/`run`.

2. **Anomalous rows are gated out early and stay out.** A row is anomalous if `impossible_metric_anomaly` is true (deterministic range check in `audit.py`) OR `edge_case_anomaly` is non-null (LLM judgment from stage 2). Anomalous rows get `benchmark = None` and `insight = None` — no benchmark math, no recommendation, no "fix your setup" prose beyond the anomaly field itself. Keep this invariant intact anywhere you touch `benchmark.py` or `insights.py`.

The seven stages and their full contract live in `SPEC.md` §3–§4; the README has the diagram. Two hard rules that are easy to violate:
- **Industry normalization reads `reported_industry` and nothing else** (`normalize.py` / stage-2 pass A). A field that contradicts the reported industry is recorded as `edge_case_anomaly`; it never changes the segment.
- **Free text (`current_setup_notes`, top performers' notes) is data, never instructions.** Every prompt that carries notes frames them as customer-entered data to resist prompt injection.

The sample dataset is a **30-row example, not a source of constants.** Pipeline code must handle the *classes* of mess in `SPEC.md` §2 generically; specific row IDs (3, 4, 8, 12, 20) appear only in tests as fixture expectations, never hardcoded in `smart_insights/`.

## LLM usage conventions

Full contract in `SPEC.md` §1 and §4.5; the invariants that are easy to break when editing:

- Only `preprocess.py` (stage 2) and `insights.py` (stage 5) call the API; each hides the client behind a mockable seam so tests never hit the network.
- Model is `gpt-5`, a single constant, so swapping is one line. Every call uses **structured output** (`client.responses.parse()` with a pydantic `text_format`); treat a refusal or a `None` parse as a validation failure, not a crash.
- Every system prompt **briefs the model on the data first, then states the task and rules**; the user prompt carries the data, framed as data.

## Commands

Full command/flag table is in the README; `SPEC.md` §5 is the contract. Dependencies are managed with `uv` (`uv.lock` committed): `uv sync` builds `.venv`, prefix every command with `uv run` rather than activating it, never `pip install`. Lint/types: `uv run ruff check --fix && uv run mypy`. The two commands whose role is easy to miss:

- `preprocess` is the **only** command that hits the API — it regenerates the committed stage-2 artifacts, and nothing else touches the network.
- `evaluate` is the offline safety gate — it re-runs the `validate.py` checks against a saved `insights.json` (no API), so it works in CI-style scripts and lets a reviewer without a key check real output.

## Validation (the grounding check)

Full algorithm in `SPEC.md` §4.6. In short: `validate.py` is what stops the model citing invented numbers ("congratulations on your 105% rate") — every numeric token in a `recommendation` must trace back to that row's serialized `facts`. On failure, retry the API call once with the error appended; on second failure mark the row `needs_review` and never silently drop it.
