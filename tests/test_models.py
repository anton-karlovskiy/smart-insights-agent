"""Stage-1 load guards: malformed rates and duplicate ids fail loudly."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from smart_insights.models import load_raw_rows


def _row(id: int, rate: float | str) -> dict[str, object]:
    return {
        "id": id,
        "website_url": f"https://site{id}.com",
        "reported_industry": "eCommerce",
        "opt_in_rate": rate,
        "current_setup_notes": "n/a",
    }


def _write(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "rows.json"
    # allow_nan=True so NaN/Infinity reach the loader as JSON literals.
    path.write_text(json.dumps(rows, allow_nan=True), encoding="utf-8")
    return path


class TestLoadRejects:
    @pytest.mark.parametrize("rate", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_rate_rejected(self, tmp_path, rate):
        """A NaN rate would slip the [0,100] audit and poison its segment's
        stats; allow_inf_nan=False stops it (and Infinity) at load."""
        with pytest.raises(ValidationError):
            load_raw_rows(_write(tmp_path, [_row(1, rate)]))

    def test_finite_rate_accepted(self, tmp_path):
        assert load_raw_rows(_write(tmp_path, [_row(1, 2.4)]))[0].opt_in_rate == 2.4

    def test_duplicate_ids_rejected(self, tmp_path):
        path = _write(tmp_path, [_row(1, 2.0), _row(2, 3.0), _row(1, 4.0)])
        with pytest.raises(ValueError, match=r"duplicate row id\(s\): \[1\]"):
            load_raw_rows(path)
