# Agentic engineering review — smart-insights-agent

A thorough, senior-level read of how this project was built: **almost no hand-written code, the whole thing steered through prompts to a coding agent (Claude Code).** This document evaluates the *method* — including its gaps — across every session consumed, not just the highlights.

Written 2026-07-15.

> **Abstract.** This is a review of *how I steered a coding agent* to build `smart-insights-agent` — not a description of what the app does. Across 232 prompts in 92 Claude Code sessions over seven days, I owned the architecture, the invariants, and the corrections; the agent (Claude Opus 4.8, with Claude Fable 5 for one review pass) did the typing. The evidence for real engineering, rather than passive generation, is concentrated in two places: the design decisions front-loaded into a spec written before any code (§2–§3), and the points where I overrode the agent — catching and correcting its own green-tested output (§5) inside a tight loop of small instructions and constant verification (§7). The claim is *direction*, not authorship: I did not write the code, but I engineered every decision that shaped it.

---

## 1. The full corpus

Measured directly from the Claude Code session transcripts on disk (`~/.claude/projects/G--anton-02-projects-smart-insights-agent/`), not from the curated writeup:

| Metric | Value |
|---|---|
| Sessions (`.jsonl` transcripts) | **115** total; 92 contained ≥1 typed prompt |
| Typed human prompts | **232** |
| Calendar span | **2026-07-09 → 07-15** (7 days) |
| Busiest days | 07-15 (67), 07-10 (42), 07-13 (41), 07-11 (40) |
| Models collaborated with | **Claude Opus 4.8** — 2,572 assistant turns (primary build/spec); **Claude Fable 5** — 548 turns (the code-review pass, §37) |
| Prompt length | median **66 chars**, max 4,737; **119 of 232 (51%)** are sub-80-char one-liners |

Two things follow immediately. First, **`PROMPTS.md` (the 38-prompt writeup this review's qualitative analysis leans on) is a ~16% curated distillation** — the load-bearing decisions lifted out of 232 raw prompts. Second, **the real texture was many small steering turns, not a few giant ones**: the median prompt is one line, and half the corpus is one-liners. The 38 curated prompts are the skeleton; the other ~194 are the muscle that moved it — commit cadence, verification loops, and micro-corrections (see §7).

---

## 2. Shape of the collaboration

The 38 curated prompts produced a complete, tested Python CLI (`python -m smart_insights`) with a committed spec, three data artifacts, and a suite that passes offline with no API key. They fall into three phases, and the ratio is the headline finding.

| Phase | Prompts | What happened | Hand-written code |
|---|---|---|---|
| **Spec authoring** | §1–§23 (23) | `SPEC.md` written and refined to a build-ready contract *before any code existed* | none |
| **Build** | §24 (1) | One instruction: build it, commit per milestone, review before advancing | none |
| **Harden & polish** | §25–§38 (14) | Tooling, readability, docs, prompt review, code-review remediation | none |

**Sixty percent of the curated prompts landed before a line of code was generated.** That is the most senior thing about the workflow: the specification was treated as the real artifact and the code as a compilation target. The build itself was one prompt because the context it compiled against had already been made unambiguous.

---

## 3. Curated prompt inventory (the load-bearing 38)

Every prompt, the move it makes, and the engineering competency it demonstrates. This is the thorough backbone; §§3–6 draw conclusions from it.

### Phase 1 — Spec authoring (§1–§23)

| # | Prompt (paraphrased) | Move | Competency |
|---|---|---|---|
| 1 | Read the brief + dataset, write `SPEC.md` for a high-quality CLI | Grounded kickoff — feed source material first | Spec-first framing |
| 2 | Add a `.gitignore` | Hygiene | Baseline discipline |
| 3 | Re-review and improve the SPEC | Self-audit loop | Iterative refinement |
| 4 | Switch the spec from Claude to OpenAI GPT | Retarget the stack cleanly | Change isolation |
| 5 | Analyze all `current_setup_notes`, write findings to a temp md | Understand the data *before* designing over it | Domain discovery |
| 6 | Use LLM (not just Python) for cleaning/normalization; add `canonical_industry_segment` | Introduce the LLM as a preprocessing tool | Hybrid-pipeline design |
| 7 | Raise "design principles" from implementation detail to architecture level | Pull the doc up an abstraction level | Altitude control |
| 8 | Split setup notes into polished passages via LLM, structured output | New field + structured-output contract | Data-shaping via LLM |
| 9 | Define the two anomaly types (deterministic `impossible_metric`, LLM `edge_case`) | Split responsibility: Python vs LLM judgment | Deterministic/LLM boundary |
| 10 | "I edited the traps section — any mistakes?" | Use the agent as reviewer of human edits | Bidirectional review |
| 11 | Harmonize terminology (user/account→website, label→segment, drop user_id) | Vocabulary lockdown across the spec | Prompt hygiene |
| 12 | Specify irrelevant-notes gating rules for §3–§8 propagation | Define what free text is *for* | Requirement precision |
| 13 | Enumerate the exact row-model fields and their None-invariants | Nail the data schema | Contract design |
| 14 | Adjudicate the AI's "five flags"; **cut thin-segment fallback** | Resolve AI judgment calls; cut scope | **Override + simplicity** |
| 15 | Make industry normalization LLM-driven, `reported_industry` only, note batch-API for scale | Generalize beyond the sample; single source of truth | Generalization + cost-awareness |
| 16 | Strip specific sample-row references from the SPEC | Decouple design from example data | Demo-vs-system distinction |
| 17 | Don't assume a fixed segment count | Remove a hidden constant | Robustness to real data |
| 18 | Emphasize prompt engineering — brief the model on the data in system prompts | Codify "context before task" | Prompt-engineering rigor |
| 19 | Define benchmarks + `top_performer_ids` ranking and the ≤3 rule | Statistical contract | Domain modeling |
| 20 | Handle the edge case where the row *is* the top performer | Probe a boundary condition | Edge-case anticipation |
| 21 | Final pre-coding SPEC review for mistakes | Gate before build | Verification discipline |
| 22 | Review the SPEC against explicit context-engineering principles | Audit context against a rubric | Meta-review |
| 23 | Summarize deliverables 2 & 3 into a separate md | Manage submission scope | Deliverable awareness |

### Phase 2 — Build (§24)

| # | Prompt | Move | Competency |
|---|---|---|---|
| 24 | Build the project with meaningful commits; review each milestone; final whole-project review | Delegate execution against a frozen contract | Milestone discipline |

The annotations under §24 record three corrections that came *out of* this build — see §4. They are the proof the "review each milestone" clause was real work, not ceremony.

### Phase 3 — Harden & polish (§25–§38)

| # | Prompt | Move | Competency |
|---|---|---|---|
| 25 | Add mypy + ruff | Static gates | Tooling |
| 26 | Whole-project readability pass, strictly behavior-preserving, tests stay green | Rename/clarify under a hard invariant | Safe refactoring |
| 27 | Rewrite README: diagram the pipeline, order the run steps, explain committed artifacts | Make the system legible to outsiders | Communication |
| 28 | Add progress bars to all commands | UX for long-running CLI | Operator experience |
| 29 | Document the model-selection TODO (one model for all tasks is a cost smell) | Record a known compromise honestly | Cost-awareness + honesty |
| 30 | Add a Claude Code PostToolUse hook to auto-run tests/types/lint/format | Automate the local gates | Workflow engineering |
| 31 | Review and improve **all** prompts against best practice + real output | Fix prompts by reading what they produced | **Override + prompt rigor** |
| 32 | Document CLI parameters in README | Close a doc gap | Completeness |
| 33 | Define "clean" rows in README | Terminology for readers | Precision |
| 34 | Define "facts" in README | Terminology for readers | Precision |
| 35 | Whole-README polish pass | Consolidate part-by-part edits | Editorial discipline |
| 36 | Review module/folder structure; reflect changes back into SPEC | Keep spec and tree in sync | Structural upkeep |
| 37 | Apply all findings from a full code review | Remediate real bugs + drift | **Override + verification** |
| 38 | Add a TODO for parallelizing insight calls (don't build it yet) | Defer optimization deliberately | Simplicity |

---

## 4. The prompting techniques, distilled

Reading down the inventory, a consistent and deliberate toolkit emerges.

**Context briefing before task.** The standing rule (§18, and enforced in the repo) is to tell the model what the data *is* — free-text CRM prose typed by a support rep — before telling it what to do. Every LLM call brief-then-tasks.

**Constraint isolation / single source of truth.** "Reference no field other than `reported_industry`" (§15); the anomaly split in §9 assigns range-checking to Python and semantic contradiction to the LLM. Boundaries are nailed shut so neither side drifts into the other's job.

**Simplicity enforced against the agent's grain.** §7, §14 (cut thin-segment fallback by name), §17, §29, §38. The AI's instinct to add fallbacks, features, and optimizations was pulled down *four separate times*. This is the discipline an agent will not supply — it builds whatever is asked.

**Generalization pressure.** §15, §16, §17 repeat one point: the sample dataset is an example, not a set of constants. Specific row IDs were scrubbed from the spec; the design was forced to handle *classes* of mess generically. This is the line between a demo and a system.

**Vocabulary lockdown (§11).** Collapsing synonyms early is what lets every later prompt land unambiguously — underrated prompt hygiene.

**Structured output as contract, not hope (§8, §15).** A refusal or `None` parse is defined as a validation failure, never a crash.

**Prompt-injection defense as a first-class concern.** Free text is framed as "data, never instructions" at every call site and asserted in tests — hostile-input thinking in a throwaway proof-of-concept.

**Meta-review prompts (§3, §10, §21, §22).** The agent was repeatedly turned on its own output *and* on the human's edits, auditing against explicit rubrics. The human used the model as a reviewer, not only a generator.

**Behavior-preserving invariants on refactors (§26).** Readability changes were bounded by "no contract/schema/prompt changes, tests stay green" — the correct way to let an agent refactor without regressing.

---

## 5. Where the human overrode the AI (the load-bearing section)

For an AI-first role, steering is proven by *corrections*, not requests. These are preserved only because the human made a policy of writing corrections into prompts rather than silently hand-editing — the one practice that makes an agentic workflow auditable after the fact.

**§14 — Five flags.** The agent surfaced five judgment calls it had made. The human adjudicated each: confirmed diagnosis-only treatment for anomalous rows, rejected verbose redundant explanations, and **entirely cut the thin-segment fallback the AI had introduced** as over-engineering. Note flag 4: the AI had also introduced a whole new `preprocess` command and committed-artifact scheme on its own initiative — defensible and ultimately kept, but a reminder that the agent will expand the architecture unless watched.

**§24 — Three corrections during the build.**
1. *Reality corrected the spec.* The AI-drafted `max_output_tokens=2048` "is plenty" ignored that gpt-5 spends reasoning tokens from the same budget. The first real run truncated mid-JSON and raised a `ValidationError` from inside `responses.parse()` — a path the AI's own error handling missed, so the batch crashed, violating the spec's own "None parse is a validation failure, not a crash" rule. Fixed in both LLM modules; the mocked suite could never have caught it.
2. *The final review found four defects in the AI's own green-tested code.* A gating invariant checked two different ways (`is not None` vs truthiness); `needs_review` rows miscounted as clean; a segment map written *before* the calls that populate it (observed live); silent last-wins on colliding keys.
3. *A blocked dependency was recorded, not papered over.* OpenAI quota ran out mid-build; artifacts were committed as clearly-labeled provisional with regeneration instructions, then genuinely regenerated as gpt-5 output when quota returned — which surfaced a Windows cp1252 crash on the model's U+2011 hyphen.

**§31 — Reading real output found three load-bearing prompt defects.** The human reviewed prompts against the GPT-5 guide *and read the committed output* to see where prose actually failed:
- Pass A asked the model to "avoid thin segments" while showing it only bare industry wordings with no website counts — an instruction it had **no way to obey.** The fix was code, not prose (`collect_variants` → `collect_variant_counts`); thin segments dropped 4→1.
- `confidence` sat in the schema with three allowed values and zero guidance, so the model emitted `medium`/`high` and **never once `low`** across 25 rows. A rubric fixed the distribution to 18/5/2.
- Field constraints lived only in the prompt string, not the JSON schema; restated as pydantic `Field(description=...)` so they ride every call.

  This is the sharpest item in the whole record: *blaming the model was diagnosed as a prompt-design bug and fixed structurally.*

**§37 — Code-review remediation.** A full-codebase review found four real (low-severity) robustness bugs invisible on the clean sample: NaN passing the range check and poisoning a whole segment's benchmarks; `--output` clobbering the committed segment map; silent duplicate-key collapse; unrejected duplicate row IDs. Plus honest spec/code drift (test counts, an undocumented `status_reason` field, nested-retry call counts). Instruction: handle all of them — and surface drift rather than silently "fix" either side.

The through-line across all four: **green tests were never taken as proof of correctness.** Every substantive bug was caught by reading real output or reviewing with whole-project context — exactly the failure classes a mocked, offline suite cannot reach.

---

## 6. The architectural spine the prompts protected

The prompts didn't just add features; they defended one decision across all 38 turns: **deterministic Python owns every statistic and decision; the LLM is used at exactly two isolated points, and only to reshape prose it is given — never to author facts or numbers.** Supporting invariants, each traceable to specific prompts and enforced in the shipped code:

- **Preprocessing is a committed artifact, not a runtime step** (§6, §14 flag 4) — so the entire suite runs offline with no API key.
- **Anomalous rows are gated out early and stay out** (§9, §13) — `benchmark` and `insight` are `None`, enforced at three independent layers (compute, facts-build, evaluate).
- **Normalization reads `reported_industry` alone** (§15) — one source of truth.
- **Validation grounds the model** — every numeric token in a recommendation must trace to that row's facts, or the row is retried once then flagged `needs_review`, never dropped (§37 finding 8 later moved one such rule from prompt to validator).

That an agent-built codebase holds a single clean invariant across 38 prompts is itself evidence the spec-first method worked.

---

## 7. Cadence and verification texture (the other ~194 prompts)

The 38 curated prompts are the decisions; the full 232-prompt corpus shows *how* they were driven. Sampling the connective tissue reveals three habits that don't show up in the writeup but define the working style.

**Commit as a heartbeat.** "Write a commit and push it" recurs dozens of times — the single most frequent prompt in the corpus. Combined with §24's "meaningful commits" instruction, this is version-control discipline enforced turn by turn, not an afterthought. (One "No no, push directly to the main" and a couple of typo'd variants — "puhs" — are visible too; the human was moving fast but deliberately.)

**Verification as a reflex, not an event.** Beyond the four formal review prompts in the writeup, the raw log is full of small checks: *"Can you review the commit changes again?"*, *"Can you review that all issues are addressed now?"*, *"Is it worth now?"*, *"Is the formatting like that OK with the rest of the content?"* The human re-checked the agent's work constantly, in small increments — the "you are in control, verify the output" principle applied as muscle memory.

**Micro-decisions kept in human hands.** Short prompts resolved small design questions the agent would otherwise have guessed: *"None or null?"*, *"RawRow / EnrichedRow is better"*, *"Add a deterministic ASCII normalizer"*, *"What does 'a single-digit segment count' mean?"* Naming, idioms, and terminology were adjudicated by the human rather than delegated — which is exactly why the finished code reads as coherent despite being machine-typed.

Taken together, the texture is the opposite of "one big prompt, walk away." It is a tight loop of small instructions and frequent verification — closer to pair programming where the human owns judgment and the agent owns typing.

---

## 8. Weaknesses and risks (a thorough review names these)

A review that only praises isn't senior. Honest gaps in the method:

- **Correctness surfaced late.** The four defects in §24 and the prompt defects in §31 existed in "green" code and shipped artifacts until a human read real output. The mocked, offline suite — a genuine strength for reproducibility — is also a blind spot: it structurally cannot catch truncation, token-budget, or prompt-quality failures. The workflow compensated with disciplined manual review, but that is a human backstop, not a systemic guard.
- **The agent expands architecture unprompted.** §14 shows it introduced both a thin-segment fallback (cut) and a whole `preprocess` command + artifact scheme (kept). Left unaudited, either could have become load-bearing without a decision being made. Constant scope vigilance was required.
- **A known cost/quality compromise still ships.** One model (`gpt-5`) for both preprocessing and insight, no per-task reasoning-effort tuning (§29), and serial insight calls (§38). Both are documented as TODOs — honest, but they are debt, not resolution.
- **Grounding is permissive by design.** The validator's numeric-token check has documented slack (comma-form numbers, `\uXXXX` escapes, digits inside IDs). Acceptable for a PoC, but it errs toward letting output through.
- **Dependence on writing corrections down.** The whole override record exists only because the human chose to prompt corrections rather than hand-edit. That is the right habit — but it's a discipline, not a guarantee; a silent hand-edit would have left no trace and broken the audit trail this review relies on.

None of these is a flaw in the *result* — the shipped code is clean, tested, and typed. They are the honest edges of an agent-driven method, and the human recognized and documented every one of them.

---

## 9. What a reviewer should take from this

- **The spec was the product.** 23 prompts of context engineering made the build a one-liner. Senior practice is front-loaded, not iterative-panic.
- **Simplicity was enforced against the agent's grain**, by name, four times.
- **Overrides are documented, not hidden.** §14/§24/§31/§37 are the real portfolio: judgment applied to AI output, which is the skill the role is hiring for.
- **Correctness was verified against reality, not tests.** Every substantive bug was caught by reading real model output or reviewing with whole-project context.
- **The method's own weaknesses are named and owned** (§8), which is itself a senior signal.

**Bottom line:** this is not "I used an AI to write code." It is a demonstration of *directing* one — owning the architecture, the invariants, the corrections, and the honest limitations — while delegating the typing.
