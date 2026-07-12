"""Validate: grounding rejects invented numbers; one-action heuristic; evaluate."""

from smart_insights.models import Insight
from smart_insights.validate import evaluate_entries, validate_insight

FACTS = {
    "id": 1,
    "website_url": "https://site1.com",
    "canonical_industry_segment": "ecommerce_retail",
    "opt_in_rate": 2.4,
    "cleaned_setup_notes": ["Sitewide popup on a 5s delay.", "Offers 10% off."],
    "benchmark": {
        "website_count": 9,
        "mean_opt_in_rate": 2.69,
        "median_opt_in_rate": 2.7,
        "min_opt_in_rate": 1.6,
        "max_opt_in_rate": 4.1,
        "canonical_industry_segment": "ecommerce_retail",
        "top_performer_ids": [7],
        "low_confidence": False,
    },
    "top_performers": [
        {"id": 7, "opt_in_rate": 4.1, "cleaned_setup_notes": ["Exit intent."]}
    ],
}


def insight(text: str) -> Insight:
    return Insight(recommendation=text, confidence="medium")


class TestGrounding:
    def test_numbers_from_facts_pass(self):
        assert validate_insight(
            insight("You convert at 2.4% vs a 2.7% segment median; the top "
                    "performer hits 4.1% with exit intent. Add an exit-intent "
                    "trigger to your 5s popup."),
            FACTS,
        ) == []

    def test_invented_number_rejected(self):
        problems = validate_insight(insight("Peers convert at 5.2%."), FACTS)
        assert problems == ["number '5.2' does not appear in this row's facts"]

    def test_leaked_105_rejected(self):
        problems = validate_insight(
            insight("Congratulations on your 105% conversion rate!"), FACTS
        )
        assert any("'105'" in p for p in problems)

    def test_small_whole_numbers_free(self):
        assert validate_insight(
            insight("Switch to a 2-step optin with one field."), FACTS
        ) == []

    def test_trailing_zeros_and_percent_normalized(self):
        # facts contain 2.7 and 10; "2.70%" and "10%" must both pass
        assert validate_insight(
            insight("The median is 2.70% and you offer 10% off."), FACTS
        ) == []


class TestSanity:
    def test_empty_rejected(self):
        assert "recommendation is empty" in validate_insight(insight("  "), FACTS)

    def test_overlong_rejected(self):
        problems = validate_insight(insight("word " * 200), FACTS)
        assert any("over the 600 limit" in p for p in problems)

    def test_multi_action_rejected(self):
        problems = validate_insight(
            insight("Add exit intent. Additionally, try a spin-to-win wheel."),
            FACTS,
        )
        assert any("exactly one action" in p for p in problems)


class TestEvaluateEntries:
    def entry(self, **overrides) -> dict:
        base = {
            **FACTS,
            "impossible_metric_anomaly": False,
            "edge_case_anomaly": None,
            "insight": {"recommendation": "Add an exit-intent trigger.",
                        "confidence": "high"},
            "status": "ok",
        }
        base.update(overrides)
        return base

    def test_valid_file_passes(self):
        assert evaluate_entries([self.entry()]) == [(1, [])]

    def test_grounding_failure_reported(self):
        bad = self.entry(insight={"recommendation": "Aim for 9.9%.",
                                  "confidence": "high"})
        [(row_id, problems)] = evaluate_entries([bad])
        assert row_id == 1 and any("'9.9'" in p for p in problems)

    def test_anomalous_row_must_have_no_benchmark_or_insight(self):
        bad = self.entry(impossible_metric_anomaly=True)
        [(_, problems)] = evaluate_entries([bad])
        assert "anomalous row has a benchmark" in problems
        assert "anomalous row has an insight" in problems

    def test_anomalous_row_with_nulls_passes(self):
        good = self.entry(
            edge_case_anomaly="Notes contradict the field.",
            benchmark=None, top_performers=None, insight=None,
        )
        assert evaluate_entries([good]) == [(1, [])]

    def test_needs_review_fails(self):
        [(_, problems)] = evaluate_entries([self.entry(status="needs_review")])
        assert problems == ["row is marked needs_review"]

    def test_llm_skipped_passes_clean_row_without_insight(self):
        assert evaluate_entries([self.entry(insight=None, status="llm_skipped")]) == [
            (1, [])
        ]
        [(_, problems)] = evaluate_entries([self.entry(insight=None, status="ok")])
        assert problems == ["clean row has no insight"]
