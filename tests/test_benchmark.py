"""Benchmark: anomalous rows excluded, stats correct, top performers ordered."""

import pytest

from smart_insights.audit import flag_impossible_rates
from smart_insights.benchmark import build_insight_facts, compute_benchmarks
from smart_insights.models import EnrichedRow


def row(
    id: int,
    rate: float,
    segment: str = "ecommerce_retail",
    edge_case: str | None = None,
    notes: list[str] | None = None,
) -> EnrichedRow:
    return EnrichedRow(
        id=id,
        website_url=f"https://site{id}.com",
        reported_industry="eCommerce",
        opt_in_rate=rate,
        current_setup_notes="raw",
        canonical_industry_segment=segment,
        cleaned_setup_notes=notes if notes is not None else [f"Setup of site {id}."],
        edge_case_anomaly=edge_case,
    )


@pytest.fixture
def rows() -> list[EnrichedRow]:
    fixture = [
        row(1, 2.4),
        row(2, 4.1),
        row(3, 3.0),
        row(4, 2.7),
        row(5, 1.6),
        row(6, 105.0),  # impossible: out of every stat
        row(7, 3.9, edge_case="Notes contradict the industry."),  # edge case: out too
        row(8, 0.9, segment="software_b2b"),
        row(9, 2.1, segment="software_b2b"),
    ]
    return compute_benchmarks(flag_impossible_rates(fixture))


class TestComputeBenchmarks:
    def test_anomalous_rows_excluded_and_unbenchmarked(self, rows):
        anomalous = {r.id: r for r in rows if r.is_anomalous}
        assert set(anomalous) == {6, 7}
        assert all(r.benchmark is None for r in anomalous.values())
        ecom = next(r for r in rows if r.id == 1).benchmark
        assert ecom.website_count == 5  # 6 and 7 not counted
        assert ecom.max_opt_in_rate == 4.1  # not 105.0 or 3.9

    def test_stats_correct(self, rows):
        b = next(r for r in rows if r.id == 1).benchmark
        assert b.mean_opt_in_rate == 2.76  # (2.4+4.1+3.0+2.7+1.6)/5
        assert b.median_opt_in_rate == 2.7
        assert b.min_opt_in_rate == 1.6
        assert b.max_opt_in_rate == 4.1
        assert b.canonical_industry_segment == "ecommerce_retail"

    def test_top_performers_strictly_better_descending_capped(self, rows):
        assert next(r for r in rows if r.id == 5).benchmark.top_performer_ids == [
            2,
            3,
            4,  # 4.1, 3.0, 2.7 — capped at three, 2.4 left out
        ]
        assert next(r for r in rows if r.id == 1).benchmark.top_performer_ids == [
            2,
            3,
            4,
        ]

    def test_segment_leader_gets_empty_list(self, rows):
        assert next(r for r in rows if r.id == 2).benchmark.top_performer_ids == []

    def test_thin_segment_flagged_low_confidence(self, rows):
        thin = next(r for r in rows if r.id == 8).benchmark
        assert thin.low_confidence is True
        healthy = next(r for r in rows if r.id == 1).benchmark
        assert healthy.low_confidence is False

    def test_other_segment_never_flagged(self):
        fixture = compute_benchmarks(
            flag_impossible_rates([row(1, 1.0, "other"), row(2, 2.0, "other")])
        )
        benchmark = fixture[0].benchmark
        assert benchmark is not None
        assert benchmark.low_confidence is False


class TestBuildInsightFacts:
    def test_joins_performer_rates_and_notes(self, rows):
        facts = build_insight_facts(next(r for r in rows if r.id == 5), rows)
        assert [p["id"] for p in facts["top_performers"]] == [2, 3, 4]
        assert facts["top_performers"][0]["opt_in_rate"] == 4.1
        assert facts["top_performers"][0]["cleaned_setup_notes"] == ["Setup of site 2."]
        assert facts["benchmark"]["top_performer_ids"] == [2, 3, 4]

    def test_anomalous_row_refused(self, rows):
        with pytest.raises(ValueError, match="anomalous rows get no facts"):
            build_insight_facts(next(r for r in rows if r.id == 6), rows)
