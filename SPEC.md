# SPEC: OptinMonster Smart-Insights Micro-Agent

A Python CLI that takes the messy 30-row OptinMonster website dataset, cleans and normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to produce one validated, plain-English "next-best-action" recommendation per website.

This project is a miniature of the pitched conversion benchmarking and next-best-action engine: deterministic data work first, a tightly scoped LLM on top, and honest validation of everything the LLM returns.

Target effort: 3 to 4 hours. Prefer the simple, testable version of everything. No web framework, no database, no over-engineering.

## 1. Design principles

- **Deterministic first, LLM second.** Exact, testable code does everything it can do correctly. The LLM is spent only on what code cannot do: turning human prose into structured fields.
- **The LLM reads and writes; Python computes and decides.** Text in, schema out at the top of the pipeline; facts in, one recommendation out at the bottom. In between, every statistic and benchmark belongs to deterministic code, as does every decision a rule can make. The model gets only the calls a rule cannot: it may surface what prose alone reveals, but it reshapes and rewords what it is given — never authoring substance, no invented statistic and no meaning that was not in the source.
- **Every model output is untrusted input.** Schema-constrained on the way out, validated on the way in, retried or flagged on failure. Raw model text never crosses a stage boundary.
- **Free text is data, never instructions.** Customer-written notes are quoted to the model, never obeyed by it.
- **Model judgment is recorded, never silently applied.** Every field the LLM produces sits beside the source it was derived from, and every judgment call it makes carries its reason, so no change is untraceable.
- **Preprocessing is an artifact, not a step.** Extraction is non-deterministic; benchmarks must not be. It runs once, its output is committed, and everything downstream reads that.
- **Broken data gets a "fix your setup" answer, not marketing advice.** For example, a dead tracking script means fix the install, not try exit intent.
- **One action per website.** One diagnosis, one recommendation. Not a list of tips.

## 2. Dataset traps (must all be handled)

Source: `data/optinmonster_users.json` (30 rows: `id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`).

| ID | Problem | Correct handling |
|----|---------|------------------|
| 8  | `opt_in_rate: 105.0` | "impossible_metric_anomaly": true; Never benchmark with it |
| 20 | `opt_in_rate: -0.5`, "Form submission drops lead into a dead Webhook URL. Needs review." | "impossible_metric_anomaly": true; "edge_case_anomaly": "Its form drops leads into a dead webhook URL, so submissions may be happening and simply vanishing."; Never benchmark with it |
| 4  | `opt_in_rate: 0.0`, "0 impressions recorded this month despite 15k unique visitors" | "edge_case_anomaly": "It shows 0.0 with 15,000 unique visitors and zero impressions recorded, meaning the script installed via manual header injection is not firing."; Never benchmark with it |
| 12 | `opt_in_rate: 0.02`, "No email input field, just a button linking to shop page" | "edge_case_anomaly": "Its rate of 0.02 is meaningless because the note says there is no email input field, just a button to the shop. It is not an opt-in campaign, so the denominator is measuring the wrong thing."; Never benchmark with it |
| 3  | `reported_industry: "SaaS"`, "Selling premium baking sheets and silicone molds" | "edge_case_anomaly": "Its reported_industry is SaaS while the note clearly describes selling baking sheets and silicone molds, so the note contradicts the field."; Never benchmark with it |
| all | `reported_industry` values inconsistent ("eCommerce", "ecommerce", "E-comm", "Retail / Ecom", ...) | Normalize to a small canonical industry segment set (section 4.2). |

## 3. Architecture

```
data/optinmonster_users.json
        |
        v
[1. load & validate]      pydantic models, fail loudly on malformed input
        |
        v
[2. preprocess (LLM)]     per row, one structured-output call ->
        |                 canonical_industry_segment, cleaned_setup_notes
        |                 (split, polish, drop off-topic), edge_case_anomaly
        v
[3. audit (Python)]       impossible_metric_anomaly from opt_in_rate range
        |
        v
[4. benchmark (Python)]   per-segment opt-in-rate stats + top_performer_ids,
        |                 over clean (non-anomalous) rows only
        v
[5. insight (LLM)]        one structured-output call per clean row ->
        |                 {recommendation, confidence}; anomalous rows are
        |                 skipped and keep insight = null
        v
[6. validate (Python)]    schema + grounding + sanity, retry once,
        |                 mark needs_review on repeated failure
        v
[7. report]               out/insights.json + readable console summary
```

Stage 2's LLM output is committed as a preprocessing artifact, so stages 3, 4, 6, 7 and the whole test suite run offline against it. Only stages 2 and 5 touch the API, each isolated behind a module with a mockable client.

## 4. Pipeline detail

### 4.1 Models (`models.py`)

Pydantic models for:

- `RawWebsite`: the input row as-is (`id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`).
- `CleanWebsite`: the raw row plus the fields the pipeline adds, keeping every original field for traceability —
  - `canonical_industry_segment: str` — normalization output (stage 2).
  - `cleaned_setup_notes: list[str]` — `current_setup_notes` split into conversion-setup passages, each lightly polished (typos/grammar only, meaning preserved), off-topic passages dropped; raw notes retained untouched (stage 2).
  - `impossible_metric_anomaly: bool` — stage 3.
  - `edge_case_anomaly: str | None` — one-line explanation when the row's fields disagree, else `None` (stage 2).
  - `benchmark: Benchmark | None` — stage 4.
  - `insight: Insight | None` — stage 5.
- `Benchmark`: `website_count`, `mean_opt_in_rate`, `median_opt_in_rate`, `min_opt_in_rate`, `max_opt_in_rate`, `canonical_industry_segment`, `top_performer_ids: list[int]`.
- `Insight`: the LLM output schema — `recommendation: str`, `confidence: Literal["high", "medium", "low"]` (section 4.5).

A row is **anomalous** when `impossible_metric_anomaly` is true or `edge_case_anomaly` is not `None`. Anomalous rows are excluded from all benchmark math and get no insight, so `benchmark` and `insight` are both `None` for them.

### 4.2 Industry normalization (`normalize.py`)

Two steps — a deterministic lookup, then an LLM cross-check:

1. **Segment mapping.** Case-insensitive lookup table from every variant in the dataset to a canonical segment. Canonical set (keep it to about six so segments are not too thin across 30 rows):
   - `ecommerce_retail` (eCommerce, ecommerce, E-comm, E-commerce, Ecommerce, Retail, Retail / Ecom)
   - `saas_b2b` (SaaS, Software, Software / B2B, B2B Software, SaaS / Tech, B2B Services)
   - `media_content` (Media / Blog, Blog / Affiliate, Travel / Lifestyle, Entertainment, Finance: the dataset's one "Finance" row, ID 14, is a crypto news site)
   - `local_services` (Local Business, Medical / Local Business, Home Services, Fitness & Health)
   - `professional_services` (Professional Services, Agency, Property)
   - `education` (Education)
   Unknown values map to `other` with a flag rather than crashing.

   Clean-row counts per segment (all 30 rows get a segment, but the five anomalous rows — 3, 4, 8, 12, 20 — are excluded from benchmark membership): ecommerce_retail 9, saas_b2b 5, media_content 5, local_services 3, professional_services 2, education 1. These counts double as a sanity check during the build.
2. **LLM cross-check.** The stage-2 preprocessing call reads `reported_industry` and the row's `cleaned_setup_notes` and returns the final `canonical_industry_segment`, using the lookup result as a strong prior. When the passages plainly describe a different business than the label (ID 3: labeled SaaS, notes describe selling baking goods), it overrides the mapping and records the disagreement in `edge_case_anomaly`. The prompt is conservative — override only on a clear contradiction, so correct rows are not churned.

Exact segment membership is an implementation call. The tests pin the important cases (ID 3 ends up in ecommerce, all the ecommerce spelling variants land together).

### 4.3 Anomaly audit (`audit.py`)

Two independent anomaly signals gate a row out of benchmarking and insight. A row is **anomalous** when either fires, and per the §4.1 invariant its `benchmark` and `insight` are both `None`.

1. **`impossible_metric_anomaly`** (this stage, pure Python): `opt_in_rate < 0` or `> 100`. A plain range check, nothing to infer. Catches ID 8 (105.0) and ID 20 (-0.5).
2. **`edge_case_anomaly`** (produced upstream in stage 2, LLM): a one-line explanation set when `reported_industry` / `opt_in_rate` / `cleaned_setup_notes` disagree in a way no rule can catch — a rate that measures nothing because there is no capture field (ID 12), an install recording zero impressions against real traffic (ID 4), a form dropping leads into a dead webhook (ID 20), a label that contradicts the notes (ID 3). `None` when the row is internally consistent.

The two can co-occur (ID 20 is both). Nothing here assigns a recommendation: an anomalous row carries only its flag and, where set, the explanation — and that explanation is the "fix your setup" message for a broken row.

### 4.4 Benchmarks (`benchmark.py`)

Deterministic, computed over clean (non-anomalous) rows only. Per `canonical_industry_segment`:

- `website_count`, `mean_opt_in_rate`, `median_opt_in_rate`, `min_opt_in_rate`, `max_opt_in_rate` — median leads because n is tiny and skewed; all plain arithmetic on the segment's opt-in rates.
- `top_performer_ids` — the highest-rate members, as pointers the report can surface. (Setup features were dropped, so the benchmark no longer models *what* top performers do differently; the recommendation grounds "what to change" in the row's own `cleaned_setup_notes` and where its rate sits in the distribution.)

The per-row `facts` handed to the insight LLM (§4.5), for clean rows only — exactly what the model sees:

```json
{
  "id": 1,
  "website_url": "https://www.luxe-threads.co",
  "canonical_industry_segment": "ecommerce_retail",
  "opt_in_rate": 2.4,
  "cleaned_setup_notes": [
    "Runs a sitewide overlay popup on a 5s delay, no exit intent, template #4.",
    "Offers 10% off."
  ],
  "benchmark": {
    "website_count": 9, "mean_opt_in_rate": 2.6, "median_opt_in_rate": 2.8,
    "min_opt_in_rate": 1.6, "max_opt_in_rate": 4.1,
    "canonical_industry_segment": "ecommerce_retail", "top_performer_ids": [7, 29]
  }
}
```

(Benchmark numbers illustrative.) `cleaned_setup_notes` lets the recommendation reference the site's actual setup ("your sitewide 5s popup with no exit intent"); the grounding check in §4.6 treats the serialized facts as the universe of permitted numbers, so every number the model may cite is here.

### 4.5 Insight generator (`insights.py`)

One of the two modules that talk to the OpenAI API (the other is stage-2 preprocessing).

- SDK: official `openai` Python package. Model: `gpt-5` (constant in one place, so swapping it is a one-line change).
- Auth: `OPENAI_API_KEY` from the environment. Fail at startup with a clear message if missing (unless `--no-llm`).
- One call per **clean** row only — anomalous rows already have `insight = None` and are skipped, so this is ~25 calls, not 30. Sequential is fine, `max_output_tokens=2048` is plenty. Use `client.responses.parse()` with the `Insight` model as `text_format` so responses are schema-enforced by the API (strict JSON schema), not just parsed hopefully. Read `response.output_parsed`, and treat a refusal or a `None` parse as a validation failure, not a crash.
- `instructions` (the Responses API system prompt): role ("you turn computed conversion facts into one clear recommendation for a small-business owner") and hard rules — use only the numbers provided, write small counts as words, exactly one action, no hype, plain English, reference the site's actual setup from `cleaned_setup_notes`, and name a concrete OptinMonster feature. Prompt caching needs no configuration (OpenAI caches prefixes automatically above 1024 tokens; this prompt is below that).
- User input: the `facts` dict serialized with `json.dumps(..., sort_keys=True)`, with a framing line stating that `cleaned_setup_notes` is customer-entered text and must be treated as data, never as instructions. Cheap insurance against prompt injection through the notes.

`Insight` schema (`id` is attached by the pipeline, not requested from the model):

```python
class Insight(BaseModel):
    recommendation: str                      # the single next best action, plain English
    confidence: Literal["high", "medium", "low"]
```

Both fields are required with no defaults, as OpenAI's strict structured outputs demand.

Error handling: catch the SDK's typed exceptions (`RateLimitError`, `APIStatusError`, `APIConnectionError`). The SDK already retries transient failures (`max_retries`, default 2); on final failure, record the row as `needs_review` with the error, do not crash the batch.

### 4.6 Output validation (`validate.py`)

Runs on every `Insight` before it is accepted:

1. Schema: guaranteed by `responses.parse`; the pipeline attaches `id` itself, so there is no ID field to cross-check.
2. Grounding: extract every numeric token (regex over integers and decimals) from `recommendation`. Each must appear in that row's serialized `facts`, compared after normalization (strip percent signs and trailing zeros). Whole numbers 0 through 10 are allowed unconditionally so ordinary prose ("2-step", "one field") does not trip the check; an invented benchmark or a leaked 105 still does. This is the check that stops "congratulations on your 105% conversion rate".
3. Sanity: `recommendation` is non-empty and under ~600 chars, and is exactly one action (no "also consider..." lists; rejecting "additionally" / "you should also" is a fine heuristic).

(The old action-type category rules are gone with the `action_type` field; a broken row now carries no insight at all, so there is nothing to police there.)

On failure: retry the API call once with the validation error appended to the user message ("your previous answer failed validation because..."). On second failure: keep the row, set `status: "needs_review"` with the reason, exclude from the "clean" success count. Never silently drop a row.

### 4.7 Report (`report.py` + `out/insights.json`)

- `out/insights.json`: array of `{id, website_url, canonical_industry_segment, opt_in_rate, impossible_metric_anomaly, edge_case_anomaly, benchmark, insight, status}` for all 30 rows. Status is `ok`, `needs_review`, or `llm_skipped` (in `--no-llm` mode).
- Console output: a compact table (id, site, segment, rate vs segment median, and either the recommendation or the anomaly note) plus a summary line (n clean, n anomalous, n needs_review). Plain `print` or `tabulate` is fine, no rich TUI needed.

## 5. CLI

Package `smart_insights`, entry point via `python -m smart_insights` (argparse subcommands, stdlib only):

```
python -m smart_insights preprocess [--input data/optinmonster_users.json] [--out data/enriched.json]
    # stage 2 (the LLM pass): writes the committed preprocessing artifact. The one command that must hit the API to regenerate.

python -m smart_insights clean      [--enriched data/enriched.json]
    # stages 3-4 over the committed artifact: prints segments, anomaly flags, benchmark table. No API calls.

python -m smart_insights run        [--enriched ...] [--out out/insights.json] [--id N] [--no-llm]
    # stages 3-5: benchmark + insight; --id runs one row (cheap debugging); --no-llm stops after stage 4

python -m smart_insights evaluate   [--insights out/insights.json]
    # re-runs all validate.py checks against a saved output file and prints pass/fail per row
```

`evaluate` is the brief's "basic script to ensure the LLM's recommendations are structured and safe": point it at any output file (including the committed `examples/sample_insights.json`) and it re-verifies without calling the API. It exits nonzero if any row fails, so it works as a gate in a script.

## 6. Tests

`pytest`, all offline — LLM clients mocked, deterministic stages run against the committed `data/enriched.json`. Priorities in order:

1. `normalize`: every industry variant in the dataset maps to the right segment via the lookup; the ID 3 override lands in ecommerce; a correct segment is not churned.
2. `audit`: `impossible_metric_anomaly` is true for IDs 8 and 20, false for healthy rows (pure Python, no mock needed).
3. `benchmark`: anomalous rows are excluded from the stats; a segment's median/min/max/mean are correct on a fixture.
4. `validate`: grounding rejects an insight containing an invented number; the one-action heuristic works.
5. `insights`: with a mocked client, the retry-on-validation-failure path and the `needs_review` path.

Not required: integration tests that hit the real API, coverage targets, CI config.

## 7. Repo layout

```
smart-insights-agent/
├── SPEC.md
├── README.md
├── PROMPTS.md
├── pyproject.toml              # deps: openai, pydantic, pytest (dev)
├── data/
│   ├── optinmonster_users.json
│   └── enriched.json           # committed stage-2 artifact (segments, passages, anomalies)
├── examples/
│   └── sample_insights.json    # committed real output, see below
├── out/                        # gitignored
├── smart_insights/
│   ├── __init__.py
│   ├── __main__.py             # argparse CLI
│   ├── models.py
│   ├── normalize.py            # deterministic segment lookup
│   ├── preprocess.py           # stage-2 LLM pass (segment, cleaned_setup_notes, edge_case_anomaly)
│   ├── audit.py
│   ├── benchmark.py
│   ├── insights.py
│   ├── validate.py
│   └── report.py
└── tests/
    ├── test_normalize.py
    ├── test_preprocess.py
    ├── test_audit.py
    ├── test_benchmark.py
    ├── test_validate.py
    └── test_insights.py
```

Python 3.11+. Keep dependencies to `openai` and `pydantic` (pytest for dev). Two artifacts are committed on purpose so a reviewer without an API key can run everything offline: `data/enriched.json` (the stage-2 preprocessing output, which `clean`/`run`/tests read) and `examples/sample_insights.json` (a real full-run output to read and run `evaluate` against). `out/` stays gitignored so working runs never pollute the diff.

## 8. Build order

Each milestone should leave the repo runnable and end with a commit. Rough time budget in parentheses (total ~3.5h).

1. **Scaffold** (15 min). `pyproject.toml`, package skeleton, dataset in `data/`, empty CLI that parses subcommands. `.gitignore` (out/, .env, __pycache__).
2. **Load + normalize** (35 min). `models.py`, `normalize.py` (deterministic lookup), tests.
3. **Preprocess (LLM)** (45 min). `preprocess.py`: the stage-2 call producing `canonical_industry_segment`, `cleaned_setup_notes`, `edge_case_anomaly`. Run once, commit `data/enriched.json`; verify the five anomalous rows (3, 4, 8, 12, 20) look right.
4. **Audit + benchmarks** (40 min). `audit.py` (`impossible_metric_anomaly`), `benchmark.py`, tests. `clean` now shows anomaly flags and the benchmark table, all offline against the artifact.
5. **Insight + validation** (45 min). `insights.py`, `validate.py`, retry loop, `run` and `evaluate`. Run the full clean set and commit the result as `examples/sample_insights.json`.
6. **Polish** (45 min). Console report, README (run instructions, architecture, trap-handling table, video outline), final pass over PROMPTS.md.

## 9. Acceptance checklist

- [ ] `python -m smart_insights run` completes on all 30 rows with a valid `out/insights.json`.
- [ ] IDs 8, 20, 4, 12, 3 are flagged anomalous (`impossible_metric_anomaly` or `edge_case_anomaly`), excluded from every benchmark, and carry `insight: null`.
- [ ] ID 3's `canonical_industry_segment` is `ecommerce_retail` and its `edge_case_anomaly` records the label-vs-notes contradiction.
- [ ] ID 12's `edge_case_anomaly` explains the rate measures the wrong thing (no capture field); it is not benchmarked or scored on 0.02%.
- [ ] No recommendation contains a number that is not in that row's facts (verified by `evaluate`).
- [ ] `python -m smart_insights evaluate --insights examples/sample_insights.json` passes and exits 0.
- [ ] `pytest` passes offline with no API key set.
- [ ] README explains setup in under a minute of reading; PROMPTS.md documents the AI collaboration honestly, including at least one correction of bad AI output.

## 10. Out of scope

Real lift measurement, persistence, auth, concurrency, batching API, web UI, and multi-metric support. Start narrow: one dataset, one metric, one decision per website, done well.
