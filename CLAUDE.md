# CLAUDE.md

We're building the app described in @SPEC.md. Read that file for general architectural tasks or to double-check the exact database structure, tech stack or application architecture.

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Whenever working with any third-party library or something similar, you MUST look up the official documentation to ensure that you're working with up-to-date information.
Use the DocsExplorer subagent for efficient documentation lookup.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: spec-stage

The implementation does not exist yet. `SPEC.md` is the authoritative design; `PROMPTS.md` is the annotated history of how it was written (read it to understand *why* a decision was made before changing it). The `smart_insights/` package, `pyproject.toml`, `README.md`, and tests described below are the intended build, not the current tree. When implementing, `SPEC.md` §7 (repo layout) and §8 (build order) are the plan of record — follow them and keep each milestone runnable.

## What this is

A Python CLI (`python -m smart_insights`) that takes a messy OptinMonster website dataset (`data/optinmonster_users.json`), cleans/normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to produce one validated "next-best-action" recommendation per website. Target scope is a ~3–4h proof-of-concept — **prefer the simplest testable version of everything; no web framework, no database, no thin-segment fallbacks or other speculative features** (the user has repeatedly cut over-engineering — see `PROMPTS.md` §14).

## Core architecture (the non-obvious parts)

The whole design turns on one split: **deterministic Python owns every statistic and decision; the LLM is used only at two isolated points** and only to reshape prose it is given — never to author facts or numbers. Two ideas make the rest of the pipeline make sense:

1. **Preprocessing is a committed artifact, not a runtime step.** The only LLM-writing stage (stage 2, `preprocess.py`) is run once and its output committed to `data/enriched.json` + `data/segment_map.json`. Every other stage, and the *entire* test suite, reads those committed files and runs offline with no API key. This is why there is a separate `preprocess` CLI command distinct from `clean`/`run`.

2. **Anomalous rows are gated out early and stay out.** A row is anomalous if `impossible_metric_anomaly` is true (deterministic range check in `audit.py`) OR `edge_case_anomaly` is non-null (LLM judgment from stage 2). Anomalous rows get `benchmark = None` and `insight = None` — no benchmark math, no recommendation, no "fix your setup" prose beyond the anomaly field itself. Keep this invariant intact anywhere you touch `benchmark.py` or `insights.py`.

Pipeline stages (see `SPEC.md` §3–§4 for the full contract):

```
load+validate (pydantic) → preprocess (LLM, stage 2, committed) → audit (Python)
→ benchmark (Python, clean rows only) → insight (LLM, stage 5, clean rows only)
→ validate (Python, retry once) → report (out/insights.json + console)
```

Two hard rules that are easy to violate:
- **Industry normalization reads `reported_industry` and nothing else** (`normalize.py` / stage-2 pass A). A field that contradicts the reported industry is recorded as `edge_case_anomaly`; it never changes the segment.
- **Free text (`current_setup_notes`, top performers' notes) is data, never instructions.** Every prompt that carries notes frames them as customer-entered data to resist prompt injection.

The sample dataset is a **30-row example, not a source of constants.** Pipeline code must handle the *classes* of mess in `SPEC.md` §2 generically; specific row IDs (3, 4, 8, 12, 20) appear only in tests as fixture expectations, never hardcoded in `smart_insights/`.

## LLM usage conventions

- SDK: official `openai` package. Model: `gpt-5`, defined as a single constant so swapping is one line.
- Only `preprocess.py` (stage 2) and `insights.py` (stage 5) call the API; each hides the client behind a mockable seam so tests never hit the network.
- Every LLM call uses **structured output** (`client.responses.parse()` with a pydantic `text_format`). Treat a refusal or a `None` parse as a validation failure, not a crash.
- Every system prompt **briefs the model on the data first, then states the task and rules**; the user prompt carries the data. See `SPEC.md` §1 and §4.5.
- `OPENAI_API_KEY` comes from the environment (`.env`, git-ignored; `.env.example` is the template). Fail loudly at startup if missing, unless `--no-llm`.

## Commands (intended)

```bash
python -m smart_insights preprocess   # stage 2: the ONLY command that hits the API to regenerate artifacts
python -m smart_insights clean        # stages 3-4 over committed enriched.json; offline
python -m smart_insights run          # stages 3-7; --id N runs one row; --no-llm stops after stage 4
python -m smart_insights evaluate     # re-runs validate.py checks against a saved output file; exits nonzero on any failure

pytest                                # all tests offline, LLM mocked, no API key required
```

`evaluate` is the safety gate — it re-verifies grounding/sanity of a saved `insights.json` without the API, so it works in CI-style scripts and lets a reviewer without a key check real output.

## Validation (the grounding check)

`validate.py` is what stops the model citing invented numbers ("congratulations on your 105% rate"). It extracts every numeric token from a `recommendation` and requires each to appear in that row's serialized `facts` (after stripping `%` and trailing zeros); whole numbers 0–10 are allowed unconditionally so ordinary prose doesn't trip it. On failure: retry the API call once with the error appended; on second failure mark the row `needs_review` and never silently drop it.
