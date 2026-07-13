"""Stage 4: deterministic per-segment benchmarks over clean rows only.

The benchmark answers "where you stand"; the facts dict built here is the
entire universe of numbers the insight LLM may cite (SPEC §4.4, §4.6).

Scaling note: joining up to three performers' notes into every facts dict
grows each insight prompt, and a segment's leaders repeat across nearly every
member's facts. Negligible at this scale; for large real-world data,
summarize each segment's top setups once, reference that shared summary from
every row's facts, and move the per-row insight calls to the Batch API
alongside the stage-2 calls (SPEC §10). Out of scope for this prototype.
"""

from __future__ import annotations

import statistics
from typing import Any

from smart_insights.models import Benchmark, EnrichedRow

# A mean over two rows is not a peer benchmark: non-"other" segments with
# fewer clean rows than this are flagged low-confidence, making the pass-A
# "avoid segments too thin to benchmark" steer checkable by code (SPEC §4.4).
MIN_SEGMENT_SIZE = 3

# How many better-performing peers a row's facts carry as exemplars (SPEC §4.4).
MAX_TOP_PERFORMERS = 3


def compute_benchmarks(rows: list[EnrichedRow]) -> list[EnrichedRow]:
    """Stamp `benchmark` on every clean row, in place. Anomalous rows keep
    benchmark = None and never enter any segment's stats."""
    clean_rows = [row for row in rows if not row.is_anomalous]
    clean_rows_by_segment: dict[str, list[EnrichedRow]] = {}
    for row in clean_rows:
        clean_rows_by_segment.setdefault(row.canonical_industry_segment, []).append(row)

    for row in clean_rows:
        segment = row.canonical_industry_segment
        # The row's own segment, itself included: website_count counts it too.
        segment_rows = clean_rows_by_segment[segment]
        segment_rates = [member.opt_in_rate for member in segment_rows]
        better_performers = sorted(
            (member for member in segment_rows if member.opt_in_rate > row.opt_in_rate),
            key=lambda member: member.opt_in_rate,
            reverse=True,
        )
        row.benchmark = Benchmark(
            website_count=len(segment_rows),
            # Rounded stats are what the insight model may cite, so keep them
            # citable (the grounding check matches against these exact tokens).
            mean_opt_in_rate=round(statistics.fmean(segment_rates), 2),
            median_opt_in_rate=round(statistics.median(segment_rates), 2),
            min_opt_in_rate=round(min(segment_rates), 2),
            max_opt_in_rate=round(max(segment_rates), 2),
            canonical_industry_segment=segment,
            top_performer_ids=[member.id for member in better_performers[:MAX_TOP_PERFORMERS]],
            low_confidence=segment != "other" and len(segment_rows) < MIN_SEGMENT_SIZE,
        )
    return rows


def build_insight_facts(row: EnrichedRow, all_rows: list[EnrichedRow]) -> dict[str, Any]:
    """The per-row facts handed to the insight LLM — exactly what the model
    sees, and the universe of permitted numbers for grounding (SPEC §4.6).
    Requires a clean, benchmarked row."""
    if row.benchmark is None:
        raise ValueError(f"row {row.id} has no benchmark; anomalous rows get no facts")
    row_by_id = {candidate.id: candidate for candidate in all_rows}
    return {
        "id": row.id,
        "website_url": row.website_url,
        "canonical_industry_segment": row.canonical_industry_segment,
        "opt_in_rate": row.opt_in_rate,
        "cleaned_setup_notes": row.cleaned_setup_notes,
        "benchmark": row.benchmark.model_dump(),
        "top_performers": [
            {
                "id": performer_id,
                "opt_in_rate": row_by_id[performer_id].opt_in_rate,
                "cleaned_setup_notes": row_by_id[performer_id].cleaned_setup_notes,
            }
            for performer_id in row.benchmark.top_performer_ids
        ],
    }
