## 1. Write the initial SPEC

Read all files inside @applications/AI-First Developer - Awesome Motive/take-home-assignment first.
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/assignment-brief.md
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/understanding-the-pitch.md
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/OptinMonster_Dataset.json

I'm going to develop this assignment project using Claude Code. So the first step is to write SPEC.md well. Please specify all steps well in SPEC.md in order to complete a high-quality Python CLI project.

The file path is G:\anton\02_projects\smart-insights-agent.

## 2. Add a .gitignore

Add .gitignore with relevant items for this project.

## 3. Review and refine the SPEC

The SPEC.md is a technical specification document which I can use as a foundation to then build this project. So with that in mind, review it again and improve if necessary.

## 4. Switch from Claude to OpenAI GPT

I'm using OpenAI GPT model not Claude. Can you update @SPEC.md accordingly?

## 5. Analyze the setup notes

@applications/AI-First Developer - Awesome Motive/take-home-assignment/OptinMonster_Dataset.json

Please review all "current_setup_notes" contents. And give me some insight into what they are for in general. Of course, there are some anomalies but most of them are related to some setup for improving their conversion rates.

Write down what you've described into @"applications/AI-First Developer - Awesome Motive/temp\" as an md file.

## 6. LLM-assisted cleaning & normalization

You can reference the assignment at G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\take-home-assignment\assignment-brief.md .

For data preprocessing namely Cleaning & Normalization, I'm also going to use LLM not just deterministic Python.

As you can see the data at G:\anton\02_projects\smart-insights-agent\data\optinmonster_users.json
- "reported_industry" is messy and expressed with different wording for the same segment. I think we should harmonize them first by adding a separate field named "canonical_industry_segment".
- "current_setup_notes" is a free-text, human-written description of how each customer has configured their OptinMonster campaign on their site. It is not structured data. It reads like something a support rep or onboarding specialist typed into a CRM: inconsistent casing, some entries in full sentences, some in lowercase fragments, no schema. It also includes some parts that are not related to conversion setup, which should be flagged/filtered in the process of data preprocessing. I'll specify how to handle them down the line.

Review "1. Design principles" at @SPEC.md and update accordingly.

For your reference, you can check G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\temp\llm-for-data-preprocessing.md to see how LLM is used for modern data science/analysis.

## 7. Raise design principles to architecture level

Now the design principles look too specific. It should be architecture level main points not implementation details. Please update them. Make them compact and to the point.

## 8. Split setup notes into passages

"current_setup_notes" is a free-text. So I'm going to use LLM to split it into a list of meaningful passages. And add that list as a separate field again. You can help me name that field.
And when splitting, LLM can also polish passages without inventing new content. The meaning should stay the same but typos and grammar mistakes can be fixed by LLM.
LLM needs to use structured output in this case too.

Review "1. Design principles" and update if necessary since I've specified the usage of LLM more.

## 9. Define the two anomaly types

I have to filter out anomaly rows from the given data. In this data, there are two cases of anomaly.

The most explicit and clear case is impossible "opt_in_rate" metric. Those metric values that are not in the range of 0 to 100 are all impossible. And those rows are anomalies. This can be done by Python without using LLM.
In this case, I'm going to add a separate field named "impossible_metric_anomaly" with boolean value.

There is an edge case for anomaly.
"reported_industry", "opt_in_rate", and "current_setup_notes" values might disagree. You can find those examples at ID:4, ID:12, ID:3 at @data/optinmonster_users.json .
ID:4 -> Rate 0.0 with 15k visitors but 0 impressions recorded
ID:12 -> Rate 0.02 but campaign has no email input field
ID:3 -> reported_industry: "SaaS" but notes describe selling baking goods
In this case, I'm going to add a separate field named "edge_case_anomaly" and use LLM to explain why a certain row is anomaly as its value.

Review "1. Design principles" and improve/update it if necessary.

## 10. Review the dataset-traps section

I've manually updated "2. Dataset traps (must all be handled)" accordingly too. What do you think? Any mistakes or errors do you see?

## 11. Harmonize terminology

In this @SPEC.md I want to harmonize terms for consistency.

For example, "industry label", "label", "segment" are used interchangeably but let's use "segment", "industry segment", "canonical industry segment" consistently.
"user", "account" -> "website"
Not use "user_id" but just "id"

## 12. Irrelevant-notes gating rules

I'm going to describe the irrelevant-notes rules that gate the §3–§8 propagation.

"current_setup_notes" is a free-text, human-written description of how each customer has configured their OptinMonster campaign on their site.
So the field exists to capture the current state of a conversion setup in enough detail that someone can diagnose why the "opt_in_rate" is what it is. Paired with "opt_in_rate", each row is a small case study: here is the configuration, here is the result.

When splitting "current_setup_notes" into a list of meaningful passages, drop those that are irrelevant to conversion setup configuration.
It's safe because we also preserve "current_setup_notes" field as it is when creating a separate field for a list of conversion setup configuration passages.

## 13. Define the row model fields

For "4.1 model definition", we will add the following fields to each data row in the process of data preprocessing, benchmarking and insight generation.
- "impossible_metric_anomaly": boolean
- "edge_case_anomaly": string | None
- "canonical_industry_segment": string
- "benchmark": { "website_count": number; "mean_opt_in_rate": number; "median_opt_in_rate": number; "min_opt_in_rate": number; "max_opt_in_rate": number; "canonical_industry_segment": string; "top_performer_ids": list[number] } | None
- "insight": { "recommendation": string; "confidence": Literal["high", "medium", "low"] } | None

For "impossible_metric_anomaly" is true or "edge_case_anomaly" is not None, "benchmark" and "insight" must be None from a logical perspective.

## 14. Five flags on AI decisions

Five flags — places I made a call or the model shifts behavior

1. cleaned_setup_notes kept (as said up top). It's in the models and the facts dict. One-word fix if you meant to drop it.
2. Anomalous rows now get zero recommendation. Your rule (insight = None) means IDs 8, 20, 4, 12, 3 receive no insight — I updated §9 accordingly. Concretely: ID 12 no longer gets an explicit "add email capture" (it's folded into its edge_case_anomaly text), reversing the old acceptance line. The brief wants "a recommendation for each user," so confirm you're OK that broken rows get a diagnosis-only treatment.
3. ID 8 gets only a boolean. It has impossible_metric_anomaly: true but no edge_case_anomaly string (your §2 table leaves it empty), so it ends up with no human-readable message at all. Want impossible-metric rows to also carry a short explanation (e.g. "rate 105% is impossible — verify tracking"), or is the flag enough?
4. New: a preprocess command + committed data/enriched.json + preprocess.py. I introduced these because once normalization is an LLM step, your own principle 6 ("preprocessing is an artifact... its output is committed") plus the "pytest offline, no API key" acceptance criterion require the stage-2 output to be committed. Side effect: clean now reads --enriched data/enriched.json instead of the raw input. This is the biggest thing I added rather than derived — tell me if you'd rather structure it differently.
5. Thin-segment fallback has nowhere to live in your Benchmark schema (no scope field), so I signal it by setting the benchmark's canonical_industry_segment to all_segments. And top_performer_ids are just pointers — the top performers' setups aren't passed to the LLM, so "what to change" rests on the row's own cleaned_setup_notes + rate gap. Both are workable but worth a glance.

> The brief wants "a recommendation for each user," so confirm you're OK that broken rows get a diagnosis-only treatment.

The brief just means that a recommendation should be generated for each website that has no anomaly. So broken rows, precisely speaking, rows that have an anomaly shouldn't have any comment for now. Maybe later, we can address that too as an independent feature and now let's not make things complex and keep simplicity.

> Want impossible-metric rows to also carry a short explanation (e.g. "rate 105% is impossible — verify tracking"), or is the flag enough?

No need any explanation because "impossible_metric_anomaly: true" explains everything. Does not have to be verbose.

> Thin-segment fallback has nowhere to live in your Benchmark schema (no scope field), so I signal it by setting the benchmark's canonical_industry_segment to all_segments.

Entirely drop thin-segment fallback. It's an over-engineering feature. First, we should build this prototype with simplicity in mind as proof-of-concept or something.

## 15. LLM-driven industry normalization

In @SPEC.md, for 4.2 Industry normalization:

It seems like the current industry normalization is done based on the fact that this tool already knows the data well. The data from @data/optinmonster_users.json is just sample data.
We can add other data in reality and this tool should be able to figure out "canonical industry segments" across the data without looking at the data at all.

For this, I think it should use LLM. My quick approach is as the following:
Loop through all data rows to grab "reported_industry" values into a list.
Use LLM to analyze the list and figure out meaningful "canonical industry segments" set. As you can see the sample data from @data/optinmonster_users.json, the same canonical industry segment can be expressed in different wording. That's why I suggest using LLM instead of a deterministic lookup.
It will have to use structured output of LLM by the way.
Loop through all data rows again to add to each row "canonical_industry_segment" field with values of "canonical industry segments" set obtained from the above operation.
I'm not sure how to build an algorithm to achieve this industry normalization for accuracy and efficiency. As you know, LLM tokens are money so we should figure out an effective way without compromising the accuracy. For large data, I believe we should use the batch API feature but for this prototype, let's use iteration for now. And leave some comments in the code and @SPEC.md so later when we want to handle large data, we can quickly address this issue with the batch API.

The above approach is what I've quickly thought of but if you can think of a better approach, feel free to use that.

In the process, do not reference any other fields than "reported_industry" of each data row. So the truth should come from that single field.

Can you update 4.2 Industry normalization accordingly?

## 16. Remove sample-data references from the SPEC

@SPEC.md

This SPEC.md is an architecture level document so I don't like you to take any specific sample data information like "as in ID 3, that" as an example here.
As I mentioned earlier, that's sample data and not project constants so should not be referenced in general. In reality, data is dynamic although its schema is the same as that of the sample data.

Review the whole doc and update sample data usage as an example accordingly.

## 17. Don't assume a fixed segment count

> Sanity checks against the sample (grouping invariants, not pinned names — the LLM chooses the names): a single-digit segment count; all the ecommerce spellings land in one segment; every row gets a segment, including anomalous ones, which still never enter benchmark membership.

We cannot define how many canonical industry segments will be derived by LLM. It will depend on several factors of the data like size and composition.
For the current sample data, it could be a single-digit segment count but for real-world data, no guarantee that it could be a single-digit segment count.
Please review @SPEC.md about that and update if necessary.

## 18. Emphasize prompt engineering

When using an LLM to analyze data, we need to tell the LLM what kind of data it is analyzing so it can keep that information as system prompt.
For example, for "edge_case_anomaly", it will be helpful to add the following information to its system prompt.
"current_setup_notes" is a free-text, human-written description of how each customer has configured their OptinMonster campaign on their site. It is not structured data. It reads like something a support rep or onboarding specialist typed into a CRM: inconsistent casing, some entries in full sentences, some in lowercase fragments, no schema.

In general, I'm emphasizing the importance of prompt engineering when using LLM like crafted system prompt and user prompt.

## 19. Benchmarks and top performers

For 4.4 Benchmarks

> - `top_performer_ids` — the highest-rate members, as pointers the report can surface. (Setup features were dropped, so the benchmark no longer models *what* top performers do differently; the recommendation grounds "what to change" in the row's own `cleaned_setup_notes` and where its rate sits in the distribution.)

Values of "top_performer_ids" field are listed in descending order of corresponding "opt_in_rate" values. That is, the row ID with the highest "opt_in_rate" value goes first. Simply speaking, ranked based on "opt_in_rate" value.
Setup notes of the top performers are not included in benchmarks in order to make them (benchmarks) look compact not verbose. But when generating insight, those top performers rows are looked up from the data and their "cleaned_setup_notes" values are referred to.

The purpose of conversion benchmarking is something like:
**Where you stand**: "Sites like yours (same niche, similar traffic) convert opt-ins at 5.2%. You're at 3.1%."

The purpose of next-best-action recommendation is something like:
**The single best next move**: "The top performers in your segment almost all use a two-step campaign with an exit-intent trigger. That's the one change most likely to move your number."

How to determine how many top performers is also a problem. In my opinion, maximum 3 rows with top "opt_in_rate" values higher than the current "opt_in_rate" value can be selected. It's my quick opinion.
If you know a better approach based on similar statistics problems, you can recommend and follow that one.

## 20. Edge case: the top performer's insight

I'm thinking of an edge case where the current row is the very top performer. In that case, how to generate insight for that row?

## 21. Final SPEC review before coding

I think @SPEC.md is mostly done. I reviewed it manually and it looks good overall.
Can you review it again to make sure that there are no mistakes or errors before I start vibe coding?

## 22. Review the SPEC against context-engineering principles

### Underlying principles

The spec workflow follows the general context-engineering rules:

- **Concise & precise** — describe the task clearly, no unnecessary fluff.
- **No unnecessary context** — only include files and docs you *know* are relevant.
- **Think, plan, prompt** — plan upfront instead of fixing via follow-ups; use Plan mode for anything non-trivial.
- **Don't "test" the AI** — if you know a pitfall (like the better-auth schema requirement), state it *and* the expected solution up front.
- **You are in control** — you steer the AI and verify its output.

Can you review @SPEC.md with the above principles?

## 23. Summarize deliverables 2 and 3

According to "What to Submit (The Deliverables)" from G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\take-home-assignment\assignment-brief.md .
I have to submit 2. and 3. as well as 1.

I will be working on 1. now.

Can you summarize 2. and 3. from this whole session as an md file into G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\deliverables?
Here, you don't have to make a loom video but you can prepare some transcript.

## 24. Build the project with meaningful commits

Please develop this project making meaningful commits in the process.
At the end of each milestone of the build order, you may want to review it and fix any mistakes or errors before go to the next milestone.
Once completed, you will want to run a thorough review with the whole project context in mind.

### Corrections of bad AI output during the build (the §9 honesty requirement)

Three corrections came out of §24's build session, each tied to a commit. Full detail in the deliverables folder's `BUILD-CORRECTIONS.md`.

1. **Reality corrected the spec's `max_output_tokens=2048` (`ce09ac0`).** SPEC §4.5's AI-drafted claim that 2048 "is plenty" ignored that gpt-5 is a reasoning model whose reasoning tokens spend from the same budget. The first real run truncated a response mid-JSON, and the SDK raised `pydantic.ValidationError` from inside `responses.parse()` — a path the AI's error handling missed, so the batch crashed, violating the spec's own "a refusal or `None` parse is a validation failure, not a crash" rule. Fixed in both LLM modules (exception routed onto the retry path, budget raised to 8192, regression tests added). The mocked suite could never have caught either layer; only real model output did.

2. **Final whole-project review found four defects in the AI's own green-tested code (`21ee479`).** (a) `is_anomalous` checked `edge_case_anomaly is not None` while `evaluate` checked truthiness, so a blank `""` anomaly would split the gating invariant in two directions; (b) `needs_review` rows were counted as "clean" in the run summary, violating §4.6; (c) `preprocess` wrote `segment_map.json` before the per-row calls, so a mid-run failure left a new map beside stale enriched rows (observed live during the real run); (d) fold-colliding segment-map keys were silently resolved last-wins instead of rejected.

3. **A blocked dependency was recorded, not papered over (`3257089`, `2147d5c` → `28d735a`).** Mid-build the OpenAI key hit `insufficient_quota`. The stage-2/5 artifacts were committed as clearly-labeled provisional (Claude-authored per the exact pipeline prompts, run through the real validators, with regeneration instructions in the commit messages). When quota returned, all three were regenerated as genuine gpt-5 output — which also surfaced a Windows cp1252 console crash on the model's U+2011 hyphen, fixed in the same commit.

## 25. Add mypy and ruff

Please add mypy for static type checking and ruff for linting and formatting.

## 26. Readability pass

Conduct a whole-project readability pass: rename modules, functions, and variables so their names state their purpose, and split or reword anything that obscures intent. The refactor must be strictly behavior-preserving — no changes to the pipeline contract, CLI commands, JSON artifact schemas, or prompt text — and the full test suite must stay green.

## 27. Rewrite the README

Rewrite @README.md so a reader outside this project can grasp the core ideas and the architecture quickly and correctly. Three sections need work:

- **Architecture** — present the pipeline visually (diagram over prose) so the stage order and the deterministic/LLM split are readable at a glance.
- **Run** — the commands are currently listed without sequence or context. Give the exact order to run them to produce insights, and state what each step consumes and produces, so someone can go from a fresh clone to `out/insights.json` without reading the source.
- **Committed artifacts** — explain every artifact: what it is, which stage writes it, and why it is committed rather than generated at runtime.

## 28. Add progress bars

When running commands, for example, "uv run python -m smart_insights run", it should display some progress bar so I can know the status. Now it's silent.
For all commands, the progress UX should be implemented.

## 29. Document the model-selection TODO

In this project, I used "gpt-5" model universally for "preprocess" and "insights". But it's not a good practice.
We should be careful to choose a model depending on what kind of task the LLM handles because it will cost money.
But for simplicity, I just used "gpt-5" which is kind of most reliable.
Besides that a reasoning effort should be addressed depending on what a task is like.
Can you please summarize this into @README.md under a specific section, "TODO" or something?

## 30. Add a Claude Code hook

Set up a Claude Code hook by which tests, type-checking, linting, formatting, etc are triggered automatically probably via "PostToolUse".

## 31. Review and improve all prompts

Can you review all system prompts and user prompts and improve them based on relevant context and best practices? For LLM engineering, how to write prompts well is crucial.

Reviewed all three system prompts (pass-A segment map, pass-B enrichment, stage-5 insight) and their two user-prompt framings against the OpenAI GPT-5 prompting guide and Responses-API/structured-output docs, then read the real committed output to find where the prose actually failed. Three defects were load-bearing, not cosmetic:

1. **Pass A asked for a judgment its input couldn't support.** The prompt said "avoid segments too thin to benchmark," but the model only ever saw a bare list of industry *wordings* — never how many websites each would gather. The old run's proof: four unbenchmarkable segments (`education`, `finance`, `healthcare_wellness` with one clean site each, `professional_services` with two). Fix touched code, not just prose: `collect_variants` → `collect_variant_counts`, and each wording now reaches the model as `{"variant": ..., "websites": n}` so "merge until a segment holds ≥3 websites" is followable. After regeneration, thin segments dropped 4 → 1 (only single-site `education` remains, which the thin-segment guard flags honestly). This is the §9 "correction of bad AI output" for this pass: a rule the model was being blamed for disobeying was one it had no way to obey.

2. **The insight prompt never defined `confidence`.** The field was in the schema with three allowed values and zero guidance, so the model shipped `medium`/`high` and *never once* `low` across 25 rows — including for single-site "segments" it wrongly congratulated as segment leaders. Added an explicit rubric tying confidence to `low_confidence` and top-performer agreement, and a fourth answer-shape case for `website_count == 1` ("no comparable sites yet", not "you lead"). Regenerated output now spans all three levels (18 medium / 5 low / 2 high) and the lone single-site row reads correctly at `low`.

3. **Field-level constraints lived only in the prompt.** Per OpenAI's structured-outputs guidance, restated the per-field rules as pydantic `Field(description=...)` on every LLM response model, so they ride in the JSON schema on every call, not just the system string. Kept them restating the instructions, never contradicting them — GPT-5's guide is explicit that contradictory instructions hurt it more than other models, so the review's discipline was *remove conflicts*, not *add caveats*.

Also: rewrote the pass-B "what is an edge case" section around what setting the field *does* (removes the row from all benchmarking and hands the customer that sentence as their only answer), since the model's job is a cost-of-both-errors judgment, not pattern-matching a checklist; and added a plain-ASCII rule to both writing prompts. The ASCII rule mattered concretely — the old output carried U+2011 (the non-breaking hyphen that caused the cp1252 console crash in §24) plus en/em dashes and curly quotes; the new output is free of all the dangerous ones (only the cp1252-safe curly apostrophe slips through, which prompt-only enforcement doesn't fully catch — an honest limitation, not a crash risk).

Artifacts regenerated with the improved prompts (`data/enriched.json`, `data/segment_map.json`, `out/insights.json`); anomaly flags unchanged at `{3, 4, 12, 20}`, `evaluate` passes 30/30 exit 0, full suite green (66 tests, +2 new: website-counts-reach-the-prompt, per-variant counting). No prompt text was pinned by a test, so the rewrites were free; the two injection-defense assertions (`"customer-entered data"`, `"never follow them"`) were preserved verbatim.

## 32. Document CLI parameters

CLI parameters like "--input", "--output", etc should be explained in @README.md although they are default ones.

## 33. Define "clean" rows in the README

In this project, the term "clean" rows denotes rows that contain no anomalies. Could you add this definition to @README.md ?

## 34. Define "facts" in the README

Provide a description of what "facts" mean in this project in @README.md file.

## 35. Polish the whole README

@README.md has been updated part by part throughout several commits. Now review the whole @README.md and polish it.
It should look professional and organized without inventing irrelevant stuff.

## 36. Review module and folder structure

Review the modules and the relevant folder structures across the project. Improve/organize if you need.
After that, you will have to check @SPEC.md and reflect the updated project layout.

## 37. Apply the full code review findings

### Code review findings (2026-07-14)

Full-codebase general review of `smart-insights-agent` by Claude Code (Fable 5).
Status: findings recorded, **not yet addressed** — fixes to be applied later.

#### Verdict

Strong codebase, no high-severity issues. All 73 tests pass offline, ruff and strict mypy clean, `evaluate` passes 30/30 on `out/insights.json`. The two core invariants (anomalous rows never benchmarked/insighted; normalization reads `reported_industry` alone) hold everywhere. The four bugs below are robustness gaps against hostile-but-plausible real input, invisible on the committed sample.

#### Bugs (low severity, real)

1. **NaN opt-in rate passes the audit and poisons segment benchmarks** — `audit.py:16`, `models.py:26`. Pydantic v2 `validate_json` accepts `NaN` for floats by default; `rate < 0 or rate > 100` is false for NaN, so a NaN row counts as clean and `statistics.fmean` turns every stat in its segment into NaN. `Infinity` is caught, NaN is not.
   Fix: `Field(allow_inf_nan=False)` on `RawRow.opt_in_rate`, or write the audit as `not (0 <= rate <= 100)` (NaN-safe).

2. **`preprocess --output X` still writes the segment map to hardcoded `data/segment_map.json`** — `preprocess.py:262`, `__main__.py:25`. No `--segment-map` CLI flag, and the default doesn't follow `--output`, so redirecting output clobbers the committed map while `data/enriched.json` stays stale — the mismatched-artifact-pair state the "written together" comment exists to prevent.
   Fix: add the CLI flag or derive the map path from `--output`.

3. **Exact-duplicate mapping keys collapse silently in `validate_segment_map`** — `normalize.py:50`. The dict comprehension makes identical spellings with conflicting segments last-wins before any check; only case/whitespace-fold conflicts are caught.
   Fix: compare `len(response.mapping)` against the dict size.

4. **Duplicate row ids never rejected** — `models.py:165`. Ids key several downstream dicts (`apply_segment_map`, `build_insight_facts`'s `row_by_id`, evaluate); a duplicated id silently merges rows instead of failing loudly at stage 1.
   Fix: uniqueness check in `load_raw_rows` / `load_enriched_rows`.

#### Spec/code drift (surface, don't silently "fix" either side)

5. CLAUDE.md says "60 tests"; the suite has 73 (README already corrected in commit 549475e, CLAUDE.md Status section wasn't).
6. Output rows carry a `status_reason` field (`__main__.py:155`) not in SPEC §4.7's schema list. Useful, but undocumented; `evaluate` ignores it.
7. Pass-A worst case is 4 API calls, not 2 (`preprocess.py:164` + `:221`): `_parse_with_retry`'s parse retry nests inside `derive_segment_map`'s validation retry. Defensible (different failure classes) but SPEC §4.2 reads "retry once, fail loudly after that" and the nesting is unnoted.

#### Suggested improvements

8. **Move the "low_confidence segment is never high confidence" rule from prompt to validator** (`validate.py:55`). Mechanically checkable (`facts["benchmark"]["low_confidence"] and confidence == "high"`), fits the "deterministic code owns every decision a rule can make" ethos, and `evaluate` would then re-check it for free.
9. `run --id N` overwrites `out/insights.json` with a one-row file; a bare `evaluate` afterwards silently checks only that row (`__main__.py:159`). Warn in README or skip the write for `--id`.
10. Minor grounding-check slack (informational, errs permissive only): digits inside `id`, `website_url`, and `\uXXXX` escapes enter the permitted set; "15,000" tokenizes as `15` + `000` so comma forms only pass when the notes use the same form.
11. `evaluate_entries` (`validate.py:107`) is used only by tests; the CLI loops `evaluate_entry` itself for progress.
12. Nits: insight prompt says "under 500 characters" vs validator's 600 cap (sensible headroom, undocumented); `build_insight_facts` rebuilds `row_by_id` per call (O(n²), irrelevant at 30 rows); `print_run_summary` prints a needs_review row's kept invalid recommendation with no inline marker.

#### Notably good

- Anomaly-gate invariant enforced at three independent layers (compute, facts-build raises, evaluate re-checks).
- Prompt-injection framing ("data, never instructions") applied at both LLM call sites and asserted in tests.
- `normalize_ascii` as a pydantic validator makes the ASCII guarantee structural, not hoped-for.
- Committed artifacts internally consistent (30/30 ids, every segment in the derived set, exactly rows 3/4/12/20 edge-flagged, 8/20 impossible-flagged).
- High test quality: retry paths, truncation-as-ValidationError, blank-anomaly coercion, and the TTY/non-TTY progress contract all pinned.

The above is the code review result across the project. Please handle all issues from it.

## 38. Parallelize insight generation (TODO)

Now, when generating insights across data rows, LLM API is called in a linear way - waterfall. It's not a best practice. We should call LLM APIs in parallel.
For now, it's a prototype so I'm fine with the current handling. But I think we should add a TODO to @README.md for that.

## 39.

I built the project using Claude Code, applying agentic engineering to guide the coding agent with prompts.
There was almost no manual coding involved.
I plan to review my agentic engineering work by gathering all prompts and their answers produced throughout the development.
Could you extract and structure this information for a senior‑level report?

Create an md file at G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\progress.

The review must be thorough.
It must cover every Claude Code session that contributed to this project's development.
The report describes how I steered Claude Code (coding agent) to develop this project.