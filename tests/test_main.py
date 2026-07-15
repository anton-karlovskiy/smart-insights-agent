"""CLI output-path routing for `run` (offline, --no-llm, no API key).

The committed out/insights.json is a tracked reference file, so `--id` must
write a separate per-row file and never overwrite it.
"""

from pathlib import Path

from smart_insights.__main__ import main

ENRICHED = str(Path(__file__).resolve().parent.parent / "data" / "enriched.json")


def test_full_run_writes_default_insights(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--no-llm", "--input", ENRICHED]) == 0
    assert (tmp_path / "out" / "insights.json").exists()


def test_id_writes_its_own_file_not_the_committed_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--no-llm", "--id", "7", "--input", ENRICHED]) == 0
    assert (tmp_path / "out" / "insights.row7.json").exists()
    # The committed full-run path is left untouched.
    assert not (tmp_path / "out" / "insights.json").exists()


def test_explicit_output_overrides_id_derivation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "custom.json"
    assert main(["run", "--no-llm", "--id", "7", "--input", ENRICHED, "--output", str(target)]) == 0
    assert target.exists()
    assert not (tmp_path / "out" / "insights.row7.json").exists()
