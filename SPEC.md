# SPEC: OptinMonster Smart-Insights Micro-Agent

A Python CLI that takes the messy 30-row OptinMonster user dataset, cleans and normalizes it, computes peer benchmarks, and uses Claude to produce one validated, plain-English "next-best-action" recommendation per user.

This is the take-home for the Awesome Motive AI-First Developer role. It is a miniature of the pitched conversion benchmarking and next-best-action engine: deterministic data work first, a tightly scoped LLM on top, and honest validation of everything the LLM returns.

Target effort: 3 to 4 hours. Prefer the simple, testable version of everything. No web framework, no database, no over-engineering.

## 1. Deliverables

1. Working Python CLI (this repo), runnable end to end with one command.
2. `PROMPTS.md`: log of prompts used with Claude Code, which models, and where AI output was manually corrected. Maintained by hand throughout, not generated at the end.
3. `README.md`: what it does, how to run it, architecture summary, and how each dataset trap is handled.
4. Loom video (3 to 5 min) walking through architecture, data hygiene, and one place the AI got something wrong. The README should end with a short outline of talking points for it.

## 2. Design principles

These come straight from the pitch and the brief. Every implementation decision defers to them.

- **The pipeline computes, the LLM words.** All numbers, benchmarks, anomaly flags, and candidate actions are produced by deterministic Python. The LLM selects and phrases the single best action from grounded facts it is handed. It never invents a statistic.
- **Trust nothing from the model.** Every LLM response is schema-validated, checked for grounding, and retried or flagged on failure. Raw text is never passed downstream.
- **Broken data gets a "fix your setup" answer, not marketing advice.** A user with a dead tracking script should be told to fix the install, not to try exit intent.
- **One action per user.** Not a list of tips. One diagnosis, one recommendation.

## 3. Dataset traps (must all be handled)

Source: `data/optinmonster_users.json` (30 rows: `id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`).

| ID | Problem | Correct handling |
|----|---------|------------------|
| 8  | `opt_in_rate: 105.0`, impossible | Quarantine metric. Recommendation type: fix tracking/verify analytics. Never benchmark with it. |
| 20 | `opt_in_rate: -0.5`, impossible; notes say webhook is dead | Quarantine metric. Recommendation type: fix the dead webhook. |
| 4  | Rate 0.0 with 15k visitors but 0 impressions recorded | Broken install, not underperformance. Recommendation type: fix script installation. |
| 12 | Rate 0.02 but campaign has no email input field | Rate is not comparable (nothing to opt into). Flag as `not_a_capture_campaign`. Recommendation: add an email capture step. |
| 3  | `reported_industry: "SaaS"` but notes describe selling baking goods | Cross-check label against notes. Reclassify to Ecommerce and flag `industry_reclassified`. |
| 27 | Notes state it duplicates ID 1's setup on another domain | Flag `duplicate_setup_of: 1`. Keep the row (it is a real site), note it in output. |
| all | Industry labels inconsistent ("eCommerce", "ecommerce", "E-comm", "Retail / Ecom", ...) | Normalize to a small canonical segment set (section 5.2). |

Rows 8, 20, and 4 are "quarantined": their rates are excluded from all benchmark math and they receive deterministic fix-type actions. Row 12's rate is also excluded from benchmarks (it measures a different thing), but the row itself is healthy enough for a normal recommendation.

## 4. Architecture

```
data/optinmonster_users.json
        |
        v
[1. load & validate]      pydantic models, fail loudly on malformed input
        |
        v
[2. normalize]            canonical industry segments, cross-check labels vs notes
        |
        v
[3. audit]                anomaly rules -> quarantine flags + data-quality notes
        |
        v
[4. enrich & benchmark]   extract setup features from notes, compute per-segment
        |                 benchmarks and gaps vs top performers (valid rows only)
        v
[5. insight generator]    one Claude call per user, structured output,
        |                 facts-only prompt (quarantined users skip the benchmark
        |                 framing and get fix-type context instead)
        v
[6. validate]             schema + grounding + action-type rules, retry once,
        |                 mark needs_review on repeated failure
        v
[7. report]               out/insights.json + readable console summary
```

Stages 1 to 4 and 6 to 7 are pure Python, fully unit-testable, no network. Stage 5 is the only API-touching code and is isolated behind one module with a mockable client.

## 5. Pipeline detail

### 5.1 Models (`models.py`)

Pydantic models for:

- `RawUser`: the input row as-is.
- `CleanUser`: adds `segment`, `flags: list[Flag]`, `metric_valid: bool`, `features: SetupFeatures`, and keeps original fields for traceability.
- `SetupFeatures`: booleans/values extracted from notes (section 5.4).
- `SegmentBenchmark`: segment name, member count, median and mean opt-in rate, top-performer feature summary.
- `Insight`: the LLM output schema (section 5.5).
- `Flag`: enum + optional detail, e.g. `impossible_metric`, `broken_install`, `dead_webhook`, `not_a_capture_campaign`, `industry_reclassified`, `duplicate_setup`, `thin_segment`.

### 5.2 Industry normalization (`normalize.py`)

Two-step, deterministic:

1. **Label mapping.** Case-insensitive lookup table from every variant in the dataset to a canonical segment. Canonical set (keep it to about six so segments are not too thin across 30 rows):
   - `ecommerce_retail` (eCommerce, ecommerce, E-comm, E-commerce, Ecommerce, Retail, Retail / Ecom)
   - `saas_b2b` (SaaS, Software, Software / B2B, B2B Software, SaaS / Tech, B2B Services)
   - `media_content` (Media / Blog, Blog / Affiliate, Travel / Lifestyle, Entertainment, Finance news/crypto sites)
   - `local_services` (Local Business, Medical / Local Business, Home Services, Fitness & Health)
   - `professional_services` (Professional Services, Agency, Property, Finance advisory)
   - `education` (Education)
   Unknown labels map to `other` with a flag rather than crashing.
2. **Notes cross-check.** A small keyword scorer over `current_setup_notes` (e.g. "selling", "checkout", "cart", "coupon", "discount code" imply ecommerce). If the notes strongly imply a different segment than the label (as in ID 3), reclassify and add `industry_reclassified` with the old and new values. Keep the keyword lists short and the threshold conservative: this must fix ID 3 without churning correct rows.

Exact segment membership is an implementation call. The tests pin the important cases (ID 3 ends up in ecommerce, all the ecommerce spelling variants land together).

### 5.3 Anomaly audit (`audit.py`)

Ordered rules, each producing a flag:

1. `opt_in_rate < 0` or `> 100` → `impossible_metric`, `metric_valid = False`.
2. Notes mention dead webhook (ID 20) → also `dead_webhook`.
3. `opt_in_rate == 0` and notes indicate zero impressions despite traffic → `broken_install`, `metric_valid = False`.
4. Notes indicate no email input field → `not_a_capture_campaign`, `metric_valid = False` (excluded from benchmarks, but not quarantined for recommendation purposes).
5. Notes declare a duplicate of another ID → `duplicate_setup` with the referenced ID.

"Quarantined" = has `impossible_metric` or `broken_install` (or `dead_webhook`). These users' pre-assigned action category is a fix action; the LLM only words the explanation.

### 5.4 Feature extraction and benchmarks (`benchmark.py`)

Extract a small, keyword-driven feature set from notes. Enough for meaningful gap analysis, no NLP heroics:

- `exit_intent` (mentions exit intent)
- `click_trigger` (2-step / MonsterLink / choice campaign)
- `lead_magnet` (discount, coupon, ebook, PDF, guide, free class/trial, spin-to-win...) and its absence
- `high_friction_form` (3+ required fields, or asks for phone/company/budget etc.)
- `instant_fullscreen` (welcome mat / takeover on load, no delay)
- `page_targeting` (specific pages: cart, checkout, schedule, articles) vs sitewide

Benchmarks, computed over `metric_valid` rows only:

- Per segment: member count, median opt-in rate (median, since n is tiny and skewed), min/max, and feature adoption rate among the segment's top half.
- If a segment has fewer than 3 valid members, fall back to the global median and flag the user's facts with `thin_segment` so the LLM frames the comparison honestly ("across all sites in this dataset" instead of "sites like yours").

Per-user output of this stage: a `facts` dict containing their rate, segment, segment benchmark, their features, the gap list (features common among top performers that they lack), and all flags. This dict is exactly what the LLM sees. Nothing else.

### 5.5 Insight generator (`insights.py`)

The only module that talks to the Claude API.

- SDK: official `anthropic` Python package. Model: `claude-opus-4-8` (constant in one place).
- Auth: `ANTHROPIC_API_KEY` from the environment. Fail at startup with a clear message if missing (unless `--no-llm`).
- One call per user (30 calls, sequential is fine). Use `client.messages.parse()` with the `Insight` Pydantic model as `output_format` so responses are schema-enforced by the API, not just parsed hopefully.
- System prompt: role ("you turn computed conversion facts into one clear recommendation for a small-business owner"), hard rules (use only the numbers provided, one action, no hype, plain English, mention concrete OptinMonster features), and the action-type definitions. Mark it with `cache_control: {"type": "ephemeral"}` so the 30 calls share a cached prefix.
- User message: the `facts` dict serialized with `json.dumps(..., sort_keys=True)`.
- For quarantined users the facts include `required_action_category: "fix_tracking"` (or `fix_webhook` / `fix_installation`) and no benchmark comparison. The prompt instructs: when a required category is present, the recommendation must be that fix.

`Insight` schema:

```python
class Insight(BaseModel):
    user_id: int
    diagnosis: str            # 1-2 sentences: where they stand and why
    action_type: ActionType   # enum, see below
    recommendation: str       # the single next best action, plain English
    expected_outcome: str     # what should improve and roughly why
    confidence: Literal["high", "medium", "low"]
```

`ActionType` enum: `fix_installation`, `fix_webhook`, `verify_tracking`, `add_email_capture`, `enable_exit_intent`, `add_lead_magnet`, `reduce_form_friction`, `add_two_step_campaign`, `improve_targeting`, `adjust_trigger`, `enable_mobile_optimization`, `maintain_and_test`.

Error handling: catch the SDK's typed exceptions (`RateLimitError`, `APIStatusError`, `APIConnectionError`). The SDK already retries transient failures; on final failure, record the user as `needs_review` with the error, do not crash the batch.

### 5.6 Output validation (`validate.py`)

Runs on every `Insight` before it is accepted:

1. Schema: guaranteed by `messages.parse`, but re-assert `user_id` matches the requested user.
2. Grounding: every number appearing in `diagnosis` / `recommendation` / `expected_outcome` must appear in that user's `facts` (string-normalized comparison, tolerate trailing zeros and a percent sign). This is the check that stops "congratulations on your 105% conversion rate".
3. Category rules: quarantined users must get their required fix-type `action_type`; non-quarantined users must not get `fix_installation`/`fix_webhook`.
4. Sanity: `recommendation` is non-empty and under ~600 chars, exactly one action (no "also consider..." lists; a simple heuristic like rejecting "additionally"/"you should also" is fine).

On failure: retry the API call once with the validation error appended to the user message ("your previous answer failed validation because..."). On second failure: keep the row, set `status: "needs_review"` with the reason, exclude from the "clean" success count. Never silently drop a user.

### 5.7 Report (`report.py` + `out/insights.json`)

- `out/insights.json`: array of `{user_id, website_url, segment, opt_in_rate, flags, benchmark: {...}, insight: {...}, status}` for all 30 users. Status is `ok`, `needs_review`, or `llm_skipped` (in `--no-llm` mode).
- Console output: a compact table (id, site, segment, rate vs segment median, action type) plus a summary line (n cleaned, n reclassified, n quarantined, n needs_review). Plain `print` formatting or `tabulate` is fine, no rich TUI needed.

## 6. CLI

Package `smart_insights`, entry point via `python -m smart_insights` (argparse subcommands, stdlib only):

```
python -m smart_insights clean    [--input data/optinmonster_users.json]
    # runs stages 1-4, prints cleaned table with segments, flags, benchmarks; no API calls

python -m smart_insights run      [--input ...] [--out out/insights.json] [--user-id N] [--no-llm]
    # full pipeline; --user-id runs one user (cheap debugging); --no-llm stops after stage 4

python -m smart_insights evaluate [--insights out/insights.json]
    # re-runs all validate.py checks against a saved output file and prints pass/fail per user
```

`evaluate` is the brief's "basic script to ensure the LLM's recommendations are structured and safe": it can be pointed at any output file and re-verifies it without calling the API.

## 7. Tests

`pytest`, all offline, LLM client mocked. Priorities in order:

1. `normalize`: every industry variant in the dataset maps to the right segment; ID 3 gets reclassified; a correct label does not get churned.
2. `audit`: IDs 8, 20, 4 quarantined with the right flags; ID 12 flagged `not_a_capture_campaign`; ID 27 flagged duplicate; healthy rows get no flags.
3. `benchmark`: quarantined rates excluded from medians; thin segments fall back to global; feature extraction spot-checks (ID 1 has no exit intent, ID 7 has it, ID 16 is high friction).
4. `validate`: grounding check rejects an insight containing an invented number; category rules reject marketing advice for a quarantined user; the one-action heuristic works.
5. `insights`: with a mocked client, the retry-on-validation-failure path and the `needs_review` path.

Not required: integration tests that hit the real API, coverage targets, CI config.

## 8. Repo layout

```
smart-insights-agent/
├── SPEC.md
├── README.md
├── PROMPTS.md
├── pyproject.toml              # deps: anthropic, pydantic, pytest (dev)
├── data/
│   └── optinmonster_users.json
├── out/                        # gitignored except .gitkeep
├── smart_insights/
│   ├── __init__.py
│   ├── __main__.py             # argparse CLI
│   ├── models.py
│   ├── normalize.py
│   ├── audit.py
│   ├── benchmark.py
│   ├── insights.py
│   ├── validate.py
│   └── report.py
└── tests/
    ├── test_normalize.py
    ├── test_audit.py
    ├── test_benchmark.py
    ├── test_validate.py
    └── test_insights.py
```

Python 3.11+. Keep dependencies to `anthropic` and `pydantic` (pytest for dev). Include one sample committed output (`out/sample_insights.json`) so a reviewer without an API key can see real results and run `evaluate` against them.

## 9. Build order

Each milestone should leave the repo runnable and end with a commit.

1. **Scaffold.** `pyproject.toml`, package skeleton, dataset in `data/`, empty CLI that parses subcommands. `.gitignore` (out/, .env, __pycache__).
2. **Load + normalize.** `models.py`, `normalize.py`, tests. `clean` command prints segments.
3. **Audit + benchmarks.** `audit.py`, `benchmark.py`, tests. `clean` now shows flags and benchmark table. All seven dataset traps visibly handled at this point, before any LLM work.
4. **Insight generator.** `insights.py` with real API calls, `run` command, `--user-id` and `--no-llm`. Verify manually on 2-3 users (one healthy, one quarantined) before running all 30.
5. **Validation + evaluate.** `validate.py`, retry loop, `evaluate` command, tests. Run the full 30 and commit `out/sample_insights.json`.
6. **Polish.** Console report, README (run instructions, architecture, trap-handling table, video outline), final pass over PROMPTS.md.

## 10. Acceptance checklist

- [ ] `python -m smart_insights run` completes on all 30 users with a valid `out/insights.json`.
- [ ] IDs 8, 20, 4 receive fix-type recommendations; none of their impossible rates appear in any benchmark.
- [ ] ID 3 is benchmarked against ecommerce peers, and the output records the reclassification.
- [ ] ID 12 is told to add an email capture, not congratulated or scolded on 0.02%.
- [ ] No recommendation contains a number that is not in that user's facts (verified by `evaluate`).
- [ ] `python -m smart_insights evaluate` passes on the committed sample output.
- [ ] `pytest` passes offline with no API key set.
- [ ] README explains setup in under a minute of reading; PROMPTS.md documents the AI collaboration honestly, including at least one correction of bad AI output.

## 11. Out of scope

Real lift measurement, persistence, auth, concurrency, batching API, web UI, and multi-metric support. The pitch's "start narrow" applies to the take-home too: one dataset, one metric, one decision per user, done well.
