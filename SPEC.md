# SPEC: OptinMonster Smart-Insights Micro-Agent

A Python CLI that takes a messy OptinMonster website dataset, cleans and normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to produce one validated, plain-English "next-best-action" recommendation per website.

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

## 2. Anomaly classes (must all be handled)

Input schema — the only fixed contract: `id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`. `data/optinmonster_users.json` is a 30-row **sample**; real data is dynamic with the same schema, so the pipeline must handle the following *classes* of mess wherever they occur. The rows below are the sample's instances of each class — worked examples for build-time verification, not project constants.

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
[2. preprocess (LLM)]     A: one dataset-level call derives the segment map
        |                 from unique reported_industry values; Python stamps
        |                 canonical_industry_segment on each row
        |                 B: per row, one structured-output call ->
        |                 cleaned_setup_notes (split, polish, drop
        |                 off-topic), edge_case_anomaly
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

- `RawRow`: the input row as-is (`id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`).
- `EnrichedRow`: the raw row plus the fields the pipeline adds, keeping every original field for traceability —
  - `canonical_industry_segment: str` — normalization output (stage 2, pass A; derived from `reported_industry` alone, §4.2).
  - `cleaned_setup_notes: list[str]` — `current_setup_notes` split into conversion-setup notes, each lightly polished (typos/grammar only, meaning preserved), off-topic notes dropped; the raw `current_setup_notes` string is retained untouched (stage 2).
  - `impossible_metric_anomaly: bool` — stage 3.
  - `edge_case_anomaly: str | None` — one-line explanation when the row's fields disagree, else `None` (stage 2).
  - `benchmark: Benchmark | None` — stage 4.
  - `insight: Insight | None` — stage 5.
- `Benchmark`: `website_count`, `mean_opt_in_rate`, `median_opt_in_rate`, `min_opt_in_rate`, `max_opt_in_rate`, `canonical_industry_segment`, `top_performer_ids: list[int]`.
- `Insight`: the LLM output schema — `recommendation: str`, `confidence: Literal["high", "medium", "low"]` (section 4.5).

A row is **anomalous** when `impossible_metric_anomaly` is true or `edge_case_anomaly` is not `None`. Anomalous rows are excluded from all benchmark math and get no insight, so `benchmark` and `insight` are both `None` for them.

### 4.2 Industry normalization (`normalize.py`)

The tool must work on data it has never seen: `data/optinmonster_users.json` is sample data, and a hardcoded variant table would only ever fit that sample. So the canonical segment set is derived from the dataset itself — and from `reported_industry` **alone**. No other field is consulted; the segment normalizes what the customer reported, it does not re-diagnose the business. (When another field contradicts `reported_industry`, that is recorded as `edge_case_anomaly` (§4.3) — it never changes the segment.)

Merging unseen wordings of the same industry ("eCommerce", "E-comm", "Retail / Ecom") is exactly the judgment a lookup table cannot make in advance, so the derivation is an LLM call — structured output, like every other model call. Everything around it stays deterministic:

1. **Collect (Python, `normalize.py`).** One pass over the rows gathers the unique `reported_industry` values (case- and whitespace-folded dedupe). Token cost then scales with distinct wordings, not row count: even a million rows collapse to a few hundred strings.
2. **Derive (LLM, one call, made from `preprocess.py`).** The deduplicated list goes into a single structured-output call returning `{segments: list[str], mapping: dict[str, str]}`. Prompt rules: merge variants that mean the same industry, keep the set small enough that segments are not too thin for the dataset's size, snake_case names, map anything unclassifiable to `other`. `normalize.py` validates the result before use — every collected variant appears as a key in `mapping`, every mapped value is in `segments`; retry once with the validation error appended, fail loudly after that.
3. **Apply (Python, `normalize.py`).** A second pass over the rows stamps `canonical_industry_segment` by plain dict lookup. No per-row LLM calls for normalization.

The derived map is committed as `data/segment_map.json` beside the enriched rows, so the model's vocabulary choice is auditable and every downstream run reads the same segments (§1: judgment recorded; preprocessing is an artifact).

Sanity checks against the sample (grouping invariants, not pinned names — the LLM chooses the names): a single-digit segment count; all the ecommerce spellings land in one segment; every row gets a segment, including anomalous ones, which still never enter benchmark membership.

Scaling note (mirror this as a code comment in `normalize.py`): the dedupe already keeps the derive call cheap, but past a few thousand distinct variants, chunk the list — and move it, along with the per-row stage-2 calls, to the OpenAI Batch API (24h completion window, ~50% discount). Out of scope for this prototype (§10).

### 4.3 Anomaly audit (`audit.py`)

Two independent anomaly signals gate a row out of benchmarking and insight. A row is **anomalous** when either fires, and per the §4.1 invariant its `benchmark` and `insight` are both `None`.

1. **`impossible_metric_anomaly`** (this stage, pure Python): `opt_in_rate < 0` or `> 100`. A plain range check, nothing to infer.
2. **`edge_case_anomaly`** (produced upstream in stage 2, LLM): a one-line explanation set when `reported_industry` / `opt_in_rate` / `cleaned_setup_notes` disagree in a way no rule can catch — a rate that measures nothing because there is no capture field, an install recording zero impressions against real traffic, a form dropping leads into a dead webhook, a `reported_industry` that contradicts the notes. `None` when the row is internally consistent.

The two can co-occur. Nothing here assigns a recommendation: an anomalous row carries only its flag and, where set, the explanation — and that explanation is the "fix your setup" message for a broken row.

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

(Benchmark numbers and segment names illustrative — the LLM derives the actual names, §4.2.) `cleaned_setup_notes` lets the recommendation reference the site's actual setup ("your sitewide 5s popup with no exit intent"); the grounding check in §4.6 treats the serialized facts as the universe of permitted numbers, so every number the model may cite is here.

### 4.5 Insight generator (`insights.py`)

One of the two modules that talk to the OpenAI API (the other is stage-2 preprocessing).

- SDK: official `openai` Python package. Model: `gpt-5` (constant in one place, so swapping it is a one-line change).
- Auth: `OPENAI_API_KEY` from the environment. Fail at startup with a clear message if missing (unless `--no-llm`).
- One call per **clean** row only — anomalous rows already have `insight = None` and are skipped. Sequential is fine, `max_output_tokens=2048` is plenty. Use `client.responses.parse()` with the `Insight` model as `text_format` so responses are schema-enforced by the API (strict JSON schema), not just parsed hopefully. Read `response.output_parsed`, and treat a refusal or a `None` parse as a validation failure, not a crash.
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

- `out/insights.json`: array of `{id, website_url, canonical_industry_segment, opt_in_rate, impossible_metric_anomaly, edge_case_anomaly, benchmark, insight, status}` for every input row. Status is `ok`, `needs_review`, or `llm_skipped` (in `--no-llm` mode).
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

`pytest`, all offline — LLM clients mocked, deterministic stages run against the committed `data/enriched.json`. Where a test pins a specific row, that is a fixture expectation against the sample, never a constant in pipeline code. Priorities in order:

1. `normalize`: the collect step dedupes variants correctly; the validator rejects a mapping that misses a variant or invents a segment (mocked LLM); against the committed artifact, all ecommerce spellings share one segment and every row's segment is in the derived set.
2. `audit`: `impossible_metric_anomaly` is true for exactly the sample rows with out-of-range rates, false for healthy rows (pure Python, no mock needed).
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
│   ├── enriched.json           # committed stage-2 artifact (segments, notes, anomalies)
│   └── segment_map.json        # committed derived segment set + variant mapping
├── examples/
│   └── sample_insights.json    # committed real output, see below
├── out/                        # gitignored
├── smart_insights/
│   ├── __init__.py
│   ├── __main__.py             # argparse CLI
│   ├── models.py
│   ├── normalize.py            # pure Python: collect variants, validate + apply the derived map
│   ├── preprocess.py           # stage-2 LLM calls: segment-map derivation + per-row notes/anomaly
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

Python 3.11+. Keep dependencies to `openai` and `pydantic` (pytest for dev). Three artifacts are committed on purpose so a reviewer without an API key can run everything offline: `data/enriched.json` and `data/segment_map.json` (the stage-2 preprocessing outputs, which `clean`/`run`/tests read) and `examples/sample_insights.json` (a real full-run output to read and run `evaluate` against). `out/` stays gitignored so working runs never pollute the diff.

## 8. Build order

Each milestone should leave the repo runnable and end with a commit. Rough time budget in parentheses (total ~3.5h).

1. **Scaffold** (15 min). `pyproject.toml`, package skeleton, dataset in `data/`, empty CLI that parses subcommands. `.gitignore` (out/, .env, __pycache__).
2. **Load + normalize** (35 min). `models.py`, `normalize.py` (collect → validate → apply, tests with the LLM mocked).
3. **Preprocess (LLM)** (45 min). `preprocess.py`: pass A derives the segment map, pass B produces per-row `cleaned_setup_notes` and `edge_case_anomaly`. Run once, commit `data/enriched.json` and `data/segment_map.json`; spot-check the sample's anomalous rows (§2) before trusting the artifact.
4. **Audit + benchmarks** (40 min). `audit.py` (`impossible_metric_anomaly`), `benchmark.py`, tests. `clean` now shows anomaly flags and the benchmark table, all offline against the artifact.
5. **Insight + validation** (45 min). `insights.py`, `validate.py`, retry loop, `run` and `evaluate`. Run the full clean set and commit the result as `examples/sample_insights.json`.
6. **Polish** (45 min). Console report, README (run instructions, architecture, trap-handling table, video outline), final pass over PROMPTS.md.

## 9. Acceptance checklist

Verified against the committed sample dataset; the specific rows cited are the sample's instances of the §2 anomaly classes, not pipeline constants.

- [ ] `python -m smart_insights run` completes on every row with a valid `out/insights.json`.
- [ ] Every §2 anomaly-class instance (in the sample: IDs 8, 20, 4, 12, 3) is flagged (`impossible_metric_anomaly` or `edge_case_anomaly`), excluded from every benchmark, and carries `insight: null`.
- [ ] A row whose notes contradict its `reported_industry` (sample: ID 3) keeps the segment its `reported_industry` implies — normalization never reads other fields — and its `edge_case_anomaly` records the contradiction.
- [ ] A row whose rate measures the wrong thing (sample: ID 12, no capture field) has an `edge_case_anomaly` saying so and is neither benchmarked nor scored on that rate.
- [ ] No recommendation contains a number that is not in that row's facts (verified by `evaluate`).
- [ ] `python -m smart_insights evaluate --insights examples/sample_insights.json` passes and exits 0.
- [ ] `pytest` passes offline with no API key set.
- [ ] README explains setup in under a minute of reading; PROMPTS.md documents the AI collaboration honestly, including at least one correction of bad AI output.

## 10. Out of scope

Real lift measurement, persistence, auth, concurrency, batching API, web UI, and multi-metric support. Start narrow: one dataset, one metric, one decision per website, done well.
