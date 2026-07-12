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


def compute_benchmarks(rows: list[EnrichedRow]) -> list[EnrichedRow]:
    """Stamp `benchmark` on every clean row, in place. Anomalous rows keep
    benchmark = None and never enter any segment's stats."""
    clean = [row for row in rows if not row.is_anomalous]
    by_segment: dict[str, list[EnrichedRow]] = {}
    for row in clean:
        by_segment.setdefault(row.canonical_industry_segment, []).append(row)

    for row in clean:
        peers = by_segment[row.canonical_industry_segment]
        rates = [peer.opt_in_rate for peer in peers]
        better = sorted(
            (peer for peer in peers if peer.opt_in_rate > row.opt_in_rate),
            key=lambda peer: peer.opt_in_rate,
            reverse=True,
        )
        segment = row.canonical_industry_segment
        row.benchmark = Benchmark(
            website_count=len(peers),
            # Rounded stats are what the insight model may cite, so keep them
            # citable (the grounding check matches against these exact tokens).
            mean_opt_in_rate=round(statistics.fmean(rates), 2),
            median_opt_in_rate=round(statistics.median(rates), 2),
            min_opt_in_rate=round(min(rates), 2),
            max_opt_in_rate=round(max(rates), 2),
            canonical_industry_segment=segment,
            top_performer_ids=[peer.id for peer in better[:3]],
            low_confidence=segment != "other" and len(peers) < MIN_SEGMENT_SIZE,
        )
    return rows


def build_facts(row: EnrichedRow, rows: list[EnrichedRow]) -> dict[str, Any]:
    """The per-row facts handed to the insight LLM — exactly what the model
    sees, and the universe of permitted numbers for grounding (SPEC §4.6).
    Requires a clean, benchmarked row."""
    if row.benchmark is None:
        raise ValueError(f"row {row.id} has no benchmark; anomalous rows get no facts")
    by_id = {r.id: r for r in rows}
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
                "opt_in_rate": by_id[performer_id].opt_in_rate,
                "cleaned_setup_notes": by_id[performer_id].cleaned_setup_notes,
            }
            for performer_id in row.benchmark.top_performer_ids
        ],
    }
