"""Normalize: collect dedupes variants; validator rejects bad maps; apply stamps."""

import pytest

from smart_insights.models import RawRow, SegmentMapResponse, VariantMapping
from smart_insights.normalize import (
    apply_segment_map,
    collect_variant_counts,
    validate_segment_map,
)


def row(id: int, industry: str) -> RawRow:
    return RawRow(
        id=id,
        website_url=f"https://site{id}.com",
        reported_industry=industry,
        opt_in_rate=1.0,
        current_setup_notes="n/a",
    )


def response(segments: list[str], mapping: dict[str, str]) -> SegmentMapResponse:
    return SegmentMapResponse(
        segments=segments,
        mapping=[VariantMapping(variant=k, segment=v) for k, v in mapping.items()],
    )


class TestCollectVariantCounts:
    def test_dedupes_case_and_whitespace(self):
        rows = [
            row(1, "eCommerce"),
            row(2, "ecommerce"),
            row(3, " ECOMMERCE "),
            row(4, "Retail / Ecom"),
            row(5, "Retail  /  Ecom"),
        ]
        counts = collect_variant_counts(rows)
        variants = list(counts)
        assert len(variants) == 2
        assert variants[0].casefold() == "ecommerce"
        assert "Retail / Ecom" in variants

    def test_counts_websites_per_folded_variant(self):
        """The pass-A prompt asks the model to avoid segments too thin to
        benchmark; it can only do that if every wording carries its website
        count, folded spellings included."""
        rows = [
            row(1, "eCommerce"),
            row(2, "ecommerce"),
            row(3, " ECOMMERCE "),
            row(4, "SaaS"),
        ]
        assert collect_variant_counts(rows) == {"eCommerce": 3, "SaaS": 1}

    def test_keeps_first_seen_spelling(self):
        assert list(collect_variant_counts([row(1, "SaaS"), row(2, "saas")])) == ["SaaS"]

    def test_deterministic_order(self):
        rows = [row(1, "Zoos"), row(2, "Agency"), row(3, "Media")]
        assert list(collect_variant_counts(rows)) == ["Agency", "Media", "Zoos"]


class TestValidateSegmentMap:
    def test_accepts_complete_map_and_returns_dict(self):
        variants = ["SaaS", "eCommerce"]
        resp = response(["saas", "ecommerce"], {"SaaS": "saas", "eCommerce": "ecommerce"})
        assert validate_segment_map(variants, resp) == {
            "SaaS": "saas",
            "eCommerce": "ecommerce",
        }

    def test_rejects_missing_variant(self):
        resp = response(["saas"], {"SaaS": "saas"})
        with pytest.raises(ValueError, match="'eCommerce' is missing"):
            validate_segment_map(["SaaS", "eCommerce"], resp)

    def test_rejects_invented_segment(self):
        resp = response(["saas"], {"SaaS": "saas", "eCommerce": "ecommerce"})
        with pytest.raises(ValueError, match="'ecommerce', which is not in segments"):
            validate_segment_map(["SaaS", "eCommerce"], resp)

    def test_rejects_exact_duplicate_variant(self):
        """Identical variant spellings collapse last-wins in the mapping dict;
        the count check catches them before that silent merge."""
        resp = SegmentMapResponse(
            segments=["saas", "ecommerce"],
            mapping=[
                VariantMapping(variant="SaaS", segment="saas"),
                VariantMapping(variant="SaaS", segment="ecommerce"),
            ],
        )
        with pytest.raises(ValueError, match="mapped more than once"):
            validate_segment_map(["SaaS"], resp)

    def test_rejects_fold_colliding_keys_with_conflicting_segments(self):
        resp = response(["saas", "ecommerce"], {"SaaS": "saas", "saas ": "ecommerce"})
        with pytest.raises(ValueError, match="differ only in case/whitespace"):
            validate_segment_map(["SaaS"], resp)

    def test_reports_every_problem_at_once(self):
        resp = response(["saas"], {"Media": "media_blog"})
        with pytest.raises(ValueError) as exc:
            validate_segment_map(["SaaS", "Media"], resp)
        assert "'SaaS' is missing" in str(exc.value)
        assert "'media_blog', which is not in segments" in str(exc.value)


class TestCommittedArtifact:
    """Fixture expectations against the committed stage-2 artifact (SPEC §6)."""

    @pytest.fixture
    def artifact(self):
        import json
        from pathlib import Path

        from smart_insights.models import load_enriched_rows

        if not Path("data/enriched.json").is_file():
            pytest.skip("stage-2 artifact not committed yet")
        rows = load_enriched_rows("data/enriched.json")
        segment_map = json.loads(Path("data/segment_map.json").read_text("utf-8"))
        return rows, segment_map

    def test_fewer_segments_than_wordings(self, artifact):
        _rows, segment_map = artifact
        assert len(segment_map["segments"]) < len(segment_map["mapping"])

    def test_all_ecommerce_spellings_share_one_segment(self, artifact):
        rows, _ = artifact
        segments = {
            r.canonical_industry_segment
            for r in rows
            if "ecom" in r.reported_industry.casefold().replace("-", "")
        }
        assert len(segments) == 1

    def test_every_row_segment_in_derived_set(self, artifact):
        rows, segment_map = artifact
        for r in rows:
            assert r.canonical_industry_segment in segment_map["segments"]

    def test_expected_edge_case_rows_flagged(self, artifact):
        """Sample instances of the §2 classes: 3, 4, 12, 20 carry an
        edge_case_anomaly; 8 (impossible rate, unremarkable notes) does not."""
        rows, _ = artifact
        flagged = {r.id for r in rows if r.edge_case_anomaly is not None}
        assert flagged == {3, 4, 12, 20}


class TestApplySegmentMap:
    def test_stamps_by_folded_lookup(self):
        rows = [row(1, "eCommerce"), row(2, "ECOMMERCE"), row(3, "SaaS")]
        mapping = {"eCommerce": "ecommerce", "SaaS": "saas"}
        assert apply_segment_map(rows, mapping) == {
            1: "ecommerce",
            2: "ecommerce",
            3: "saas",
        }

    def test_uncovered_variant_fails_loudly(self):
        with pytest.raises(KeyError, match="row 1"):
            apply_segment_map([row(1, "Mystery")], {"SaaS": "saas"})
