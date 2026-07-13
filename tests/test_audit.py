"""Audit: impossible_metric_anomaly is a pure range check on opt_in_rate."""

from pathlib import Path

import pytest

from smart_insights.audit import flag_impossible_rates, is_impossible_rate
from smart_insights.models import load_enriched_rows

ARTIFACT = Path("data/enriched.json")


@pytest.mark.parametrize(
    ("rate", "impossible"),
    [
        (105.0, True),
        (-0.5, True),
        (100.001, True),
        (-0.0001, True),
        (0.0, False),
        (100.0, False),
        (2.4, False),
        (0.02, False),
    ],
)
def test_range_check(rate: float, impossible: bool):
    assert is_impossible_rate(rate) is impossible


@pytest.mark.skipif(not ARTIFACT.is_file(), reason="stage-2 artifact not committed yet")
def test_sample_rows_flagged_exactly():
    """Fixture expectation against the committed sample: rows 8 (105.0) and
    20 (-0.5) are the only out-of-range rates."""
    rows = flag_impossible_rates(load_enriched_rows(ARTIFACT))
    flagged = {row.id for row in rows if row.impossible_metric_anomaly}
    assert flagged == {8, 20}
