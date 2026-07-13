"""Stage 3: deterministic anomaly audit.

`impossible_metric_anomaly` is a plain range check — nothing to infer.
The other gate, `edge_case_anomaly`, was produced upstream in stage 2 and is
already on the row. Either one makes the row anomalous (models.EnrichedRow
.is_anomalous), which excludes it from benchmarks and insights.
"""

from __future__ import annotations

from smart_insights.models import EnrichedRow


def is_impossible_rate(opt_in_rate: float) -> bool:
    """An opt-in rate is a percentage: outside [0, 100] is impossible."""
    return opt_in_rate < 0 or opt_in_rate > 100


def flag_impossible_rates(rows: list[EnrichedRow]) -> list[EnrichedRow]:
    """Stamp impossible_metric_anomaly on every row, in place."""
    for row in rows:
        row.impossible_metric_anomaly = is_impossible_rate(row.opt_in_rate)
    return rows
