"""Stage 7: out/insights.json rows + readable console summaries. Plain print."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smart_insights.models import EnrichedRow


def output_row(row: EnrichedRow, facts: dict[str, Any] | None, status: str) -> dict:
    """One out/insights.json entry: carries everything the grounding check
    reads (§4.6), so `evaluate` can re-verify from the file alone, offline."""
    return {
        "id": row.id,
        "website_url": row.website_url,
        "canonical_industry_segment": row.canonical_industry_segment,
        "opt_in_rate": row.opt_in_rate,
        "cleaned_setup_notes": row.cleaned_setup_notes,
        "impossible_metric_anomaly": row.impossible_metric_anomaly,
        "edge_case_anomaly": row.edge_case_anomaly,
        "benchmark": row.benchmark.model_dump() if row.benchmark else None,
        "top_performers": facts["top_performers"] if facts else None,
        "insight": row.insight.model_dump() if row.insight else None,
        "status": status,
    }


def write_insights(entries: list[dict], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def print_segment_table(rows: list[EnrichedRow]) -> None:
    """The `clean` view: id, site, segment, rate, anomaly flags, benchmark."""
    print(
        f"{'id':>3}  {'site':<38} {'segment':<22} {'rate':>7}  "
        f"{'seg med':>7}  anomaly"
    )
    for row in rows:
        anomaly = ""
        if row.impossible_metric_anomaly:
            anomaly = "impossible_metric"
        if row.edge_case_anomaly:
            anomaly = (anomaly + " + " if anomaly else "") + "edge_case"
        median = f"{row.benchmark.median_opt_in_rate}" if row.benchmark else "-"
        flag = " (low-confidence)" if row.benchmark and row.benchmark.low_confidence else ""
        print(
            f"{row.id:>3}  {_fit(row.website_url, 38):<38} "
            f"{row.canonical_industry_segment:<22} {row.opt_in_rate:>7}  "
            f"{median:>7}  {anomaly}{flag}"
        )
    clean = sum(1 for r in rows if not r.is_anomalous)
    print(f"\n{len(rows)} rows: {clean} clean, {len(rows) - clean} anomalous")


def print_run_summary(entries: list[dict]) -> None:
    """The `run` view: recommendation or anomaly note per row, then totals."""
    for entry in entries:
        rate = entry["opt_in_rate"]
        benchmark = entry["benchmark"]
        median = benchmark["median_opt_in_rate"] if benchmark else None
        standing = f"{rate} vs median {median}" if median is not None else f"{rate}"
        if entry["insight"]:
            text = entry["insight"]["recommendation"]
            text += f"  [confidence: {entry['insight']['confidence']}]"
        elif entry["edge_case_anomaly"]:
            text = f"ANOMALY: {entry['edge_case_anomaly']}"
        elif entry["impossible_metric_anomaly"]:
            text = "ANOMALY: impossible opt_in_rate (outside 0-100)"
        else:
            text = f"(no insight: {entry['status']})"
        print(f"--- {entry['id']}: {entry['website_url']}")
        print(f"    {entry['canonical_industry_segment']} | opt-in {standing} | {entry['status']}")
        print(f"    {text}")

    total = len(entries)
    anomalous = sum(
        1 for e in entries if e["impossible_metric_anomaly"] or e["edge_case_anomaly"]
    )
    needs_review = sum(1 for e in entries if e["status"] == "needs_review")
    # needs_review rows are excluded from the clean success count (§4.6).
    print(
        f"\n{total} rows: {total - anomalous - needs_review} clean, "
        f"{anomalous} anomalous, {needs_review} needs_review"
    )
