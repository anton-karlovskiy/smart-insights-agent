# OptinMonster Smart-Insights Micro-Agent

A Python CLI that takes a messy OptinMonster website dataset, cleans and
normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to
produce one validated, plain-English "next-best-action" recommendation per
website. Deterministic code owns every statistic and decision; the LLM only
reshapes prose it is given — never authoring facts or numbers. Full design:
[SPEC.md](SPEC.md); AI-collaboration history: [PROMPTS.md](PROMPTS.md).

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                              # add OPENAI_API_KEY (only needed
                                                  # for `preprocess` and full `run`)
```

## Run

```bash
pytest                                # all offline: LLM mocked, no API key needed

python -m smart_insights clean       # segments, anomaly flags, benchmark table (offline)
python -m smart_insights run --no-llm         # stages 3-4, writes out/insights.json (offline)
python -m smart_insights run                  # full pipeline incl. LLM insights (needs key)
python -m smart_insights run --id 7           # one row (cheap debugging)
python -m smart_insights evaluate --insights examples/sample_insights.json
                                      # re-verify a committed real output, offline, exit 0/1

python -m smart_insights preprocess   # regenerate the committed stage-2 artifacts
                                      # (the ONE command that must hit the API)
```

## Checks

```bash
ruff format                           # format
ruff check --fix                      # lint (E, F, I, UP, B, SIM, RUF)
mypy                                  # static types, strict over smart_insights/ and tests/
```

## Architecture

```
load+validate (pydantic) → preprocess (LLM, committed artifact) → audit (Python)
→ benchmark (Python, clean rows only) → insight (LLM, clean rows only)
→ validate (Python, retry once) → report (out/insights.json + console)
```

Two ideas carry the design:

1. **Preprocessing is a committed artifact, not a runtime step.** The only
   LLM-writing stage runs once (`preprocess`) and its output is committed as
   `data/enriched.json` + `data/segment_map.json`. Every other stage — and the
   whole test suite — reads those files and runs offline.
2. **Anomalous rows are gated out early and stay out.** A deterministic range
   check (`impossible_metric_anomaly`) or an LLM-recorded contradiction
   (`edge_case_anomaly`) excludes a row from every benchmark and from insight
   generation: its `benchmark` and `insight` stay `null`, and the anomaly
   explanation *is* its "fix your setup" answer.

The LLM appears at exactly two points, both structured-output calls behind
mockable seams: deriving the industry-segment vocabulary + cleaning each row's
notes (stage 2), and turning computed facts into one recommendation (stage 5).
`validate.py` then requires every number in a recommendation to appear in that
row's facts — a failed check retries once with the error appended, then marks
the row `needs_review`.

## Trap handling (sample dataset)

| ID | Trap | Handling |
|----|------|----------|
| 8  | `opt_in_rate: 105.0` | `impossible_metric_anomaly: true`; never benchmarked |
| 20 | rate `-0.5` **and** notes describe a dead webhook | both flags: impossible metric + `edge_case_anomaly` (leads vanishing) |
| 4  | rate `0.0`, 0 impressions vs 15k visitors | `edge_case_anomaly`: tracking script not firing |
| 12 | rate `0.02`, no email field at all | `edge_case_anomaly`: rate measures the wrong thing |
| 3  | `reported_industry: SaaS`, notes sell bakeware | segment stays what `reported_industry` implies (normalization never reads other fields); the contradiction is recorded as `edge_case_anomaly` |
| all | "eCommerce" / "E-comm" / "Retail / Ecom" ... | segment set derived from the data by one LLM call, validated in code, committed as `data/segment_map.json` |

Anomaly **classes**, not row IDs, drive the pipeline — the IDs above are just
the sample's instances, asserted in tests, never hardcoded in `smart_insights/`.

## Committed artifacts

Three artifacts are committed on purpose so a reviewer without an API key can
run everything offline: `data/enriched.json` + `data/segment_map.json` (real
gpt-5 stage-2 output, read by `clean`/`run`/tests) and
`examples/sample_insights.json` (a real full-run output — all 30 rows pass
`evaluate`). Regenerate them with `preprocess` and `run` respectively.

## Video outline (3-4 min)

1. The dataset: 30 messy rows — impossible rates, dead trackers, contradicting
   industries (30s).
2. `clean`: derived segments, anomaly gating, benchmark table — all offline,
   all deterministic (45s).
3. `run` on one row: the facts dict (the model's entire universe), the one
   recommendation back (60s).
4. `evaluate`: the grounding check catching an invented number; `needs_review`
   instead of silent failure (45s).
5. Architecture recap: LLM at two points only, committed artifacts, everything
   else testable Python (30s).
