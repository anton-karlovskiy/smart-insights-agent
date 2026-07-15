"""Stage 6: schema + grounding + sanity checks on every Insight.

The grounding check is what stops the model citing invented numbers
("congratulations on your 105% rate"): every numeric token in the
recommendation must appear in that row's serialized facts.
"""

from __future__ import annotations

import json
import re
from typing import Any

from smart_insights.models import Insight

# Headroom over the "under 500" the prompt asks for: the model aiming at 500
# should not be failed for landing at 540, but a runaway paragraph still trips.
MAX_RECOMMENDATION_CHARS = 600

# Whole numbers 0-10 pass unconditionally so ordinary prose ("2-step",
# "one of the three") never trips the check; an invented benchmark or a
# leaked 105 still does.
ALWAYS_ALLOWED_NUMBERS = {str(n) for n in range(11)}

_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")

# One-action heuristic: phrases that signal a list of tips, not one action.
_MULTI_ACTION_PHRASES = ("additionally", "also consider", "you should also", "another option")

# The fields benchmark.build_insight_facts put in front of the model. An output
# row carries every one of them, so `evaluate` can rebuild the facts a saved
# recommendation was grounded in and re-check it offline.
_FACTS_KEYS_IN_OUTPUT_ROW = (
    "id",
    "website_url",
    "canonical_industry_segment",
    "opt_in_rate",
    "cleaned_setup_notes",
    "benchmark",
    "top_performers",
)


def _canonical_number(token: str) -> str:
    """Compare numbers after stripping trailing zeros ("5.0" == "5")."""
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token


def permitted_numbers(facts: dict[str, Any]) -> set[str]:
    """The serialized facts are the universe of permitted numbers."""
    serialized_facts = json.dumps(facts, sort_keys=True)
    return {_canonical_number(token) for token in _NUMBER_TOKEN.findall(serialized_facts)}


def validate_insight(insight: Insight, facts: dict[str, Any]) -> list[str]:
    """All the output-validation checks; returns every problem found (empty list = valid).
    Percent signs need no special handling: the token regex captures only
    the digits of "5.2%"."""
    problems: list[str] = []

    recommendation = insight.recommendation.strip()
    if not recommendation:
        problems.append("recommendation is empty")
    if len(recommendation) > MAX_RECOMMENDATION_CHARS:
        problems.append(
            f"recommendation is {len(recommendation)} chars, "
            f"over the {MAX_RECOMMENDATION_CHARS} limit"
        )
    lowercased = recommendation.lower()
    for phrase in _MULTI_ACTION_PHRASES:
        if phrase in lowercased:
            problems.append(f"recommendation must be exactly one action, but contains {phrase!r}")

    allowed_numbers = permitted_numbers(facts)
    for token in _NUMBER_TOKEN.findall(recommendation):
        if token in ALWAYS_ALLOWED_NUMBERS:
            continue
        if _canonical_number(token) not in allowed_numbers:
            problems.append(f"number {token!r} does not appear in this row's facts")

    # "A segment flagged low_confidence is never high" is a rule code can check,
    # so enforce it here rather than trusting the prompt; evaluate re-checks it.
    benchmark = facts.get("benchmark")
    if benchmark and benchmark.get("low_confidence") and insight.confidence == "high":
        problems.append("confidence is 'high' but the segment is flagged low_confidence")

    return problems


def evaluate_entry(entry: dict[str, Any]) -> list[str]:
    """Re-run every check against one saved output row (the report schema) — the row
    carries everything the grounding check reads, so this works offline.
    Returns the problems found; an empty list means the row passes."""
    problems: list[str] = []
    is_anomalous = entry["impossible_metric_anomaly"] or entry["edge_case_anomaly"]
    if is_anomalous:
        # The invariant: anomalous rows get no benchmark and no insight.
        if entry["benchmark"] is not None:
            problems.append("anomalous row has a benchmark")
        if entry["insight"] is not None:
            problems.append("anomalous row has an insight")
    elif entry["status"] == "needs_review":
        problems.append("row is marked needs_review")
    elif entry["insight"] is None:
        if entry["status"] != "llm_skipped":
            problems.append("clean row has no insight")
    else:
        facts = {key: entry[key] for key in _FACTS_KEYS_IN_OUTPUT_ROW}
        problems.extend(validate_insight(Insight(**entry["insight"]), facts))
    return problems


def evaluate_entries(entries: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    """Every saved output row checked: (id, problems) per row; all-empty
    problems means the file passes."""
    return [(entry["id"], evaluate_entry(entry)) for entry in entries]
