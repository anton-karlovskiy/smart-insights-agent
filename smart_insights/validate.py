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

MAX_RECOMMENDATION_CHARS = 600

# Whole numbers 0-10 pass unconditionally so ordinary prose ("2-step",
# "one of the three") never trips the check; an invented benchmark or a
# leaked 105 still does.
FREE_SMALL_INTS = {str(n) for n in range(11)}

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# One-action heuristic: phrases that signal a list of tips, not one action.
_MULTI_ACTION = ("additionally", "also consider", "you should also", "another option")


def _normalize(token: str) -> str:
    """Compare numbers after stripping trailing zeros ("5.0" == "5")."""
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token


def permitted_numbers(facts: dict[str, Any]) -> set[str]:
    """The serialized facts are the universe of permitted numbers (§4.4)."""
    serialized = json.dumps(facts, sort_keys=True)
    return {_normalize(token) for token in _NUMBER.findall(serialized)}


def validate_insight(insight: Insight, facts: dict[str, Any]) -> list[str]:
    """All §4.6 checks; returns every problem found (empty list = valid).
    Percent signs need no special handling: the token regex captures only
    the digits of "5.2%"."""
    problems: list[str] = []

    text = insight.recommendation.strip()
    if not text:
        problems.append("recommendation is empty")
    if len(text) > MAX_RECOMMENDATION_CHARS:
        problems.append(
            f"recommendation is {len(text)} chars, over the {MAX_RECOMMENDATION_CHARS} limit"
        )
    lowered = text.lower()
    for phrase in _MULTI_ACTION:
        if phrase in lowered:
            problems.append(f"recommendation must be exactly one action, but contains {phrase!r}")

    allowed = permitted_numbers(facts)
    for token in _NUMBER.findall(text):
        if token in FREE_SMALL_INTS:
            continue
        if _normalize(token) not in allowed:
            problems.append(f"number {token!r} does not appear in this row's facts")

    return problems


def evaluate_entries(entries: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    """Re-run every check against saved output rows (§4.7 schema) — each row
    carries everything the grounding check reads, so this works offline.
    Returns (id, problems) per row; all-empty problems means the file passes."""
    results: list[tuple[int, list[str]]] = []
    for entry in entries:
        problems: list[str] = []
        anomalous = entry["impossible_metric_anomaly"] or entry["edge_case_anomaly"]
        if anomalous:
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
            facts = {
                key: entry[key]
                for key in (
                    "id",
                    "website_url",
                    "canonical_industry_segment",
                    "opt_in_rate",
                    "cleaned_setup_notes",
                    "benchmark",
                    "top_performers",
                )
            }
            problems.extend(validate_insight(Insight(**entry["insight"]), facts))
        results.append((entry["id"], problems))
    return results
