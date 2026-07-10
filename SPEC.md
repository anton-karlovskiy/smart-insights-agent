# SPEC: OptinMonster Smart-Insights Micro-Agent

A Python CLI that takes the messy 30-row OptinMonster user dataset, cleans and normalizes it, computes peer benchmarks, and uses an OpenAI GPT model to produce one validated, plain-English "next-best-action" recommendation per user.

This project is a miniature of the pitched conversion benchmarking and next-best-action engine: deterministic data work first, a tightly scoped LLM on top, and honest validation of everything the LLM returns.

Target effort: 3 to 4 hours. Prefer the simple, testable version of everything. No web framework, no database, no over-engineering.

## 1. Design principles

- **Deterministic first, LLM second.** Exact, testable code does everything it can do correctly. The LLM is spent only on what code cannot do: turning human prose into structured fields.
- **The LLM reads and writes; Python computes and decides.** Text in, schema out at the top of the pipeline; facts in, one recommendation out at the bottom. Every number, rule, and verdict in between belongs to deterministic code. A model reshapes and rewords what it is given; it never authors substance — no invented statistic, and no meaning that was not in the source.
- **Every model output is untrusted input.** Schema-constrained on the way out, validated on the way in, retried or flagged on failure. Raw model text never crosses a stage boundary.
- **Free text is data, never instructions.** Customer-written notes are quoted to the model, never obeyed by it.
- **Model judgment is recorded, never silently applied.** Whatever the LLM overrides keeps its original value alongside the reason, so every change is auditable.
- **Preprocessing is an artifact, not a step.** Extraction is non-deterministic; benchmarks must not be. It runs once, its output is committed, and everything downstream reads that.
- **Broken data gets a "fix your setup" answer, not marketing advice.** For example, a dead tracking script means fix the install, not try exit intent.
- **One action per user.** One diagnosis, one recommendation. Not a list of tips.

## 2. Dataset traps (must all be handled)

Source: `data/optinmonster_users.json` (30 rows: `id`, `website_url`, `reported_industry`, `opt_in_rate`, `current_setup_notes`).

| ID | Problem | Correct handling |
|----|---------|------------------|
| 8  | `opt_in_rate: 105.0`, impossible | Quarantine metric. Required action category: `verify_tracking`. Never benchmark with it. |
| 20 | `opt_in_rate: -0.5`, impossible; notes say webhook is dead | Quarantine metric. Required action category: `fix_webhook`. |
| 4  | Rate 0.0 with 15k visitors but 0 impressions recorded | Broken install, not underperformance. Required action category: `fix_installation`. |
| 12 | Rate 0.02 but campaign has no email input field | Rate is not comparable (nothing to opt into). Flag as `not_a_capture_campaign`. Recommendation: add an email capture step. |
| 3  | `reported_industry: "SaaS"` but notes describe selling baking goods | Cross-check label against notes. Reclassify to Ecommerce and flag `industry_reclassified`. |
| 27 | Notes state it duplicates ID 1's setup on another domain | Flag `duplicate_setup_of: 1`. Keep the row (it is a real site), note it in output. |
| all | Industry labels inconsistent ("eCommerce", "ecommerce", "E-comm", "Retail / Ecom", ...) | Normalize to a small canonical segment set (section 4.2). |

Rows 8, 20, and 4 are "quarantined": their rates are excluded from all benchmark math and they receive deterministic fix-type actions. Row 12's rate is also excluded from benchmarks (it measures a different thing), but the row itself is healthy enough for a normal recommendation.

## 3. Architecture

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
[5. insight generator]    one OpenAI call per user, structured output,
        |                 facts-only prompt (quarantined users skip the benchmark
        |                 framing and get fix-type context instead)
        v
[6. validate]             schema + grounding + action-type rules, retry once,
        |                 mark needs_review on repeated failure
        v
[7. report]               out/insights.json + readable console summary
```

Stages 1 to 4 and 6 to 7 are pure Python, fully unit-testable, no network. Stage 5 is the only API-touching code and is isolated behind one module with a mockable client.

## 4. Pipeline detail

### 4.1 Models (`models.py`)

Pydantic models for:

- `RawUser`: the input row as-is.
- `CleanUser`: adds `segment`, `flags: list[Flag]`, `metric_valid: bool`, `features: SetupFeatures`, and keeps original fields for traceability.
- `SetupFeatures`: booleans/values extracted from notes (section 4.4).
- `SegmentBenchmark`: segment name, member count, median and mean opt-in rate, top-performer feature summary.
- `Insight`: the LLM output schema (section 4.5).
- `Flag`: enum + optional detail, e.g. `impossible_metric`, `broken_install`, `dead_webhook`, `not_a_capture_campaign`, `industry_reclassified`, `duplicate_setup`, `thin_segment`.

### 4.2 Industry normalization (`normalize.py`)

Two-step, deterministic:

1. **Label mapping.** Case-insensitive lookup table from every variant in the dataset to a canonical segment. Canonical set (keep it to about six so segments are not too thin across 30 rows):
   - `ecommerce_retail` (eCommerce, ecommerce, E-comm, E-commerce, Ecommerce, Retail, Retail / Ecom)
   - `saas_b2b` (SaaS, Software, Software / B2B, B2B Software, SaaS / Tech, B2B Services)
   - `media_content` (Media / Blog, Blog / Affiliate, Travel / Lifestyle, Entertainment, Finance: the dataset's one "Finance" row, ID 14, is a crypto news site)
   - `local_services` (Local Business, Medical / Local Business, Home Services, Fitness & Health)
   - `professional_services` (Professional Services, Agency, Property)
   - `education` (Education)
   Unknown labels map to `other` with a flag rather than crashing.

   Expected sizes with this mapping, after ID 3 is reclassified and invalid metrics are excluded: ecommerce_retail 10 valid, saas_b2b 5, media_content 5, local_services 3, professional_services 2, education 1. So the thin-segment fallback in 4.4 is not hypothetical: professional_services and education will use it. These counts double as a sanity check during the build.
2. **Notes cross-check.** A small keyword scorer over `current_setup_notes` (e.g. "selling", "checkout", "cart", "coupon", "discount code" imply ecommerce). If the notes strongly imply a different segment than the label (as in ID 3), reclassify and add `industry_reclassified` with the old and new values. Keep the keyword lists short and the threshold conservative: this must fix ID 3 without churning correct rows.

Exact segment membership is an implementation call. The tests pin the important cases (ID 3 ends up in ecommerce, all the ecommerce spelling variants land together).

### 4.3 Anomaly audit (`audit.py`)

Ordered rules, each producing a flag:

1. `opt_in_rate < 0` or `> 100` → `impossible_metric`, `metric_valid = False`.
2. Notes mention dead webhook (ID 20) → also `dead_webhook`.
3. `opt_in_rate == 0` and notes indicate zero impressions despite traffic → `broken_install`, `metric_valid = False`.
4. Notes indicate no email input field → `not_a_capture_campaign`, `metric_valid = False` (excluded from benchmarks, but not quarantined for recommendation purposes).
5. Notes declare a duplicate of another ID → `duplicate_setup` with the referenced ID.

"Quarantined" = has `impossible_metric` or `broken_install` (or `dead_webhook`). The audit assigns each quarantined user its required action category from the trap table (ID 8 → `verify_tracking`, ID 20 → `fix_webhook`, ID 4 → `fix_installation`); the LLM only words the explanation.

### 4.4 Feature extraction and benchmarks (`benchmark.py`)

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

Per-user output of this stage: a `facts` dict. This dict is exactly what the LLM sees, nothing else. It includes the raw `setup_notes` verbatim: the recommendation should reference the user's actual setup ("your 10% discount", "your welcome mat"), and the grounding check in 4.6 treats the serialized facts as the universe of permitted numbers, so the notes must be inside it. Example for ID 1 (benchmark numbers illustrative):

```json
{
  "user_id": 1,
  "website_url": "https://www.luxe-threads.co",
  "segment": "ecommerce_retail",
  "opt_in_rate": 2.4,
  "metric_valid": true,
  "flags": [],
  "setup_notes": "Runs a sitewide overlay popup on 5s delay, no exit intent, template #4. Offers 10% off.",
  "features": {"exit_intent": false, "click_trigger": false, "lead_magnet": true,
               "high_friction_form": false, "instant_fullscreen": false, "page_targeting": false},
  "benchmark": {"scope": "segment", "member_count": 10, "median_opt_in_rate": 2.8,
                "top_performer_features": ["exit_intent", "page_targeting"]},
  "gaps": ["exit_intent", "page_targeting"],
  "required_action_category": null
}
```

For quarantined users, `benchmark` and `gaps` are null and `required_action_category` carries the audit's assigned fix category. For thin segments, `benchmark.scope` is `"global"`.

### 4.5 Insight generator (`insights.py`)

The only module that talks to the OpenAI API.

- SDK: official `openai` Python package. Model: `gpt-5` (constant in one place, so swapping it is a one-line change).
- Auth: `OPENAI_API_KEY` from the environment. Fail at startup with a clear message if missing (unless `--no-llm`).
- One call per user (30 calls, sequential is fine, `max_output_tokens=2048` is plenty). Use `client.responses.parse()` with the `Insight` Pydantic model as `text_format` so responses are schema-enforced by the API (strict JSON schema), not just parsed hopefully. Read the result off `response.output_parsed`, and treat a refusal or a `None` parse as a validation failure, not a crash.
- `instructions` (the Responses API's system prompt): role ("you turn computed conversion facts into one clear recommendation for a small-business owner"), hard rules (use only the numbers provided, write small counts as words, one action, no hype, plain English, mention concrete OptinMonster features), and the action-type definitions. Nothing to configure for prompt caching: OpenAI caches prefixes automatically above 1024 tokens, this prompt is below that, and there is no marker to set either way.
- User input: the `facts` dict serialized with `json.dumps(..., sort_keys=True)`, with a framing line stating that `setup_notes` is customer-entered text and must be treated as data, never as instructions. Cheap insurance against prompt injection through the notes field.
- When `required_action_category` is set, the prompt instructs that `action_type` must be that category and the recommendation must be that fix, with no benchmark framing.

`Insight` schema (`user_id` is attached by the pipeline, not requested from the model: one less field to get wrong):

```python
class Insight(BaseModel):
    diagnosis: str            # 1-2 sentences: where they stand and why
    action_type: ActionType   # enum, see below
    recommendation: str       # the single next best action, plain English
    expected_outcome: str     # what should improve and roughly why
    confidence: Literal["high", "medium", "low"]
```

`ActionType` enum: `fix_installation`, `fix_webhook`, `verify_tracking`, `add_email_capture`, `enable_exit_intent`, `add_lead_magnet`, `reduce_form_friction`, `add_two_step_campaign`, `improve_targeting`, `adjust_trigger`, `enable_mobile_optimization`, `maintain_and_test`.

Every field is required and there are no defaults, which is what OpenAI's strict structured outputs demand.

Error handling: catch the SDK's typed exceptions (`RateLimitError`, `APIStatusError`, `APIConnectionError`). The SDK already retries transient failures (`max_retries`, default 2); on final failure, record the user as `needs_review` with the error, do not crash the batch.

### 4.6 Output validation (`validate.py`)

Runs on every `Insight` before it is accepted:

1. Schema: guaranteed by `responses.parse`; the pipeline attaches `user_id` itself, so there is no ID field to cross-check.
2. Grounding: extract every numeric token (regex over integers and decimals) from `diagnosis` / `recommendation` / `expected_outcome`. Each must appear in that user's serialized `facts`, compared after normalization (strip percent signs and trailing zeros). Whole numbers 0 through 10 are allowed unconditionally so ordinary prose ("2-step", "one field") does not trip the check; an invented benchmark or a leaked 105 still does. This is the check that stops "congratulations on your 105% conversion rate".
3. Category rules: quarantined users must get their required `action_type`; non-quarantined users must not get `fix_installation`, `fix_webhook`, or `verify_tracking`.
4. Sanity: `recommendation` is non-empty and under ~600 chars, exactly one action (no "also consider..." lists; a simple heuristic like rejecting "additionally"/"you should also" is fine).

On failure: retry the API call once with the validation error appended to the user message ("your previous answer failed validation because..."). On second failure: keep the row, set `status: "needs_review"` with the reason, exclude from the "clean" success count. Never silently drop a user.

### 4.7 Report (`report.py` + `out/insights.json`)

- `out/insights.json`: array of `{user_id, website_url, segment, opt_in_rate, flags, benchmark: {...}, insight: {...}, status}` for all 30 users. Status is `ok`, `needs_review`, or `llm_skipped` (in `--no-llm` mode).
- Console output: a compact table (id, site, segment, rate vs segment median, action type) plus a summary line (n cleaned, n reclassified, n quarantined, n needs_review). Plain `print` formatting or `tabulate` is fine, no rich TUI needed.

## 5. CLI

Package `smart_insights`, entry point via `python -m smart_insights` (argparse subcommands, stdlib only):

```
python -m smart_insights clean    [--input data/optinmonster_users.json]
    # runs stages 1-4, prints cleaned table with segments, flags, benchmarks; no API calls

python -m smart_insights run      [--input ...] [--out out/insights.json] [--user-id N] [--no-llm]
    # full pipeline; --user-id runs one user (cheap debugging); --no-llm stops after stage 4

python -m smart_insights evaluate [--insights out/insights.json]
    # re-runs all validate.py checks against a saved output file and prints pass/fail per user
```

`evaluate` is the brief's "basic script to ensure the LLM's recommendations are structured and safe": it can be pointed at any output file (including the committed `examples/sample_insights.json`) and re-verifies it without calling the API. It exits nonzero if any user fails, so it works as a gate in a script.

## 6. Tests

`pytest`, all offline, LLM client mocked. Priorities in order:

1. `normalize`: every industry variant in the dataset maps to the right segment; ID 3 gets reclassified; a correct label does not get churned.
2. `audit`: IDs 8, 20, 4 quarantined with the right flags; ID 12 flagged `not_a_capture_campaign`; ID 27 flagged duplicate; healthy rows get no flags.
3. `benchmark`: quarantined rates excluded from medians; thin segments fall back to global; feature extraction spot-checks (ID 1 has no exit intent, ID 7 has it, ID 16 is high friction).
4. `validate`: grounding check rejects an insight containing an invented number; category rules reject marketing advice for a quarantined user; the one-action heuristic works.
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
│   └── optinmonster_users.json
├── examples/
│   └── sample_insights.json    # committed real output, see below
├── out/                        # gitignored
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

Python 3.11+. Keep dependencies to `openai` and `pydantic` (pytest for dev). `examples/sample_insights.json` is a real full-run output committed on purpose: a reviewer without an API key can read actual results and run `evaluate` against them. `out/` stays gitignored so working runs never pollute the diff.

## 8. Build order

Each milestone should leave the repo runnable and end with a commit. Rough time budget in parentheses (total ~3.5h).

1. **Scaffold** (15 min). `pyproject.toml`, package skeleton, dataset in `data/`, empty CLI that parses subcommands. `.gitignore` (out/, .env, __pycache__).
2. **Load + normalize** (40 min). `models.py`, `normalize.py`, tests. `clean` command prints segments.
3. **Audit + benchmarks** (45 min). `audit.py`, `benchmark.py`, tests. `clean` now shows flags and benchmark table. All seven dataset traps visibly handled at this point, before any LLM work.
4. **Insight generator** (40 min). `insights.py` with real API calls, `run` command, `--user-id` and `--no-llm`. Verify manually on 2-3 users (one healthy, one quarantined) before running all 30.
5. **Validation + evaluate** (45 min). `validate.py`, retry loop, `evaluate` command, tests. Run the full 30 and commit the result as `examples/sample_insights.json`.
6. **Polish** (45 min). Console report, README (run instructions, architecture, trap-handling table, video outline), final pass over PROMPTS.md.

## 9. Acceptance checklist

- [ ] `python -m smart_insights run` completes on all 30 users with a valid `out/insights.json`.
- [ ] IDs 8, 20, 4 receive fix-type recommendations; none of their impossible rates appear in any benchmark.
- [ ] ID 3 is benchmarked against ecommerce peers, and the output records the reclassification.
- [ ] ID 12 is told to add an email capture, not congratulated or scolded on 0.02%.
- [ ] No recommendation contains a number that is not in that user's facts (verified by `evaluate`).
- [ ] `python -m smart_insights evaluate --insights examples/sample_insights.json` passes and exits 0.
- [ ] `pytest` passes offline with no API key set.
- [ ] README explains setup in under a minute of reading; PROMPTS.md documents the AI collaboration honestly, including at least one correction of bad AI output.

## 10. Out of scope

Real lift measurement, persistence, auth, concurrency, batching API, web UI, and multi-metric support. Start narrow: one dataset, one metric, one decision per user, done well.
