# Solution Walkthrough — Loom Video

A short async screen-share walking through the Smart Insights Agent. I recorded it in four parts so each topic stays focused and easy to skip back to — together they run about four and a half minutes.

Quick map of what each part covers:

## 1. What it is + architectural choices
🎥 https://www.loom.com/share/aae2e8c648944f40a0d69666baa377f1

The one decision the whole design turns on: deterministic Python owns every statistic and every decision, and the LLM appears at only two of the seven stages, where it reshapes prose it's handed — never authoring a fact or a number. Also why preprocessing is a committed artifact rather than a runtime step, so the tests run offline with no key.

## 2. Data hygiene and edge cases
🎥 https://www.loom.com/share/98f97608332f4a82a5e93ee54054b113

Why the segment vocabulary is derived from the data instead of a hardcoded lookup, so nothing is fitted to the 30-row sample. Then how edge cases are handled by *gating* — anomalous rows are flagged early and get a diagnosis, not marketing advice — and the grounding check that traces every number in a recommendation back to that row's facts.

## 3. Where the AI gave me bad logic, and the fix
🎥 https://www.loom.com/share/a00177afa954455fb390d67c053b6e72

A concrete one: the agent set `max_output_tokens` too low and called it "plenty", ignoring that GPT-5 spends reasoning tokens from the same budget. Every test was green because the tests mock the API — the first real run truncated JSON mid-response and crashed the batch. How I caught it and corrected both LLM modules.

## 4. Close — the workflow
🎥 https://www.loom.com/share/245cf3771bd548c992ceedd108cb920d

A quick word on process: spec-first, most of the prompting done before any code was generated, and the known cost trade-offs documented as deliberate TODOs rather than hidden.
