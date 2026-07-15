"""Industry normalization: pure Python around the one LLM derivation call.

Collect (here) -> derive (LLM, in preprocess.py) -> validate + apply (here).
The canonical segment set is derived from `reported_industry` ALONE — no other
field is consulted; contradictions belong in `edge_case_anomaly`, never here.

Scaling note: the dedupe already keeps the derive call cheap (token cost
scales with distinct wordings, not row count), but past a few thousand
distinct variants, chunk the list and move it, with the per-row stage-2
calls, to the Batch API. Out of scope for this prototype.
"""

from __future__ import annotations

from smart_insights.models import RawRow, SegmentMapResponse


def _lookup_key(wording: str) -> str:
    """Dedupe/lookup key for an industry wording: case-folded, whitespace-
    collapsed, so "eCommerce", "ecommerce" and " ECOMMERCE " are one variant."""
    return " ".join(wording.split()).casefold()


def collect_variant_counts(rows: list[RawRow]) -> dict[str, int]:
    """Unique reported_industry wordings -> how many websites reported each.
    First-seen spelling kept, deduped case- and whitespace-insensitively,
    deterministic order.

    The counts exist for the pass-A prompt: a segment is a benchmarking peer
    group, so the model is asked to avoid segments too thin to benchmark
    — a judgment it cannot make from a bare list of wordings.
    """
    first_spelling_by_key: dict[str, str] = {}
    websites_by_key: dict[str, int] = {}
    for row in rows:
        key = _lookup_key(row.reported_industry)
        if key not in first_spelling_by_key:
            first_spelling_by_key[key] = row.reported_industry.strip()
        websites_by_key[key] = websites_by_key.get(key, 0) + 1
    return {
        first_spelling_by_key[key]: websites_by_key[key]
        for key in sorted(first_spelling_by_key, key=_lookup_key)
    }


def validate_segment_map(variants: list[str], response: SegmentMapResponse) -> dict[str, str]:
    """Check the LLM's map covers every variant and invents no segment;
    return it as a plain variant->segment dict. Raises ValueError with every
    problem listed, so a retry prompt can carry the full error."""
    mapping = {pair.variant: pair.segment for pair in response.mapping}
    declared_segments = set(response.segments)

    problems: list[str] = []
    segment_by_key: dict[str, str] = {}
    for mapped_variant, segment in mapping.items():
        key = _lookup_key(mapped_variant)
        if key in segment_by_key and segment_by_key[key] != segment:
            problems.append(
                f"mapping keys that differ only in case/whitespace disagree "
                f"on the segment for {mapped_variant!r}"
            )
        segment_by_key[key] = segment
    for variant in variants:
        if _lookup_key(variant) not in segment_by_key:
            problems.append(f"variant {variant!r} is missing from the mapping")
    for mapped_variant, segment in mapping.items():
        if segment not in declared_segments:
            problems.append(
                f"variant {mapped_variant!r} maps to {segment!r}, which is not in segments"
            )
    if problems:
        raise ValueError("; ".join(problems))
    return mapping


def apply_segment_map(rows: list[RawRow], mapping: dict[str, str]) -> dict[int, str]:
    """Stamp every row's canonical segment by plain dict lookup (folded key).
    Returns row id -> segment. Every row gets a segment, anomalous ones
    included. Raises KeyError if a row's wording is not covered."""
    segment_by_key = {_lookup_key(variant): segment for variant, segment in mapping.items()}
    segment_by_row_id: dict[int, str] = {}
    for row in rows:
        key = _lookup_key(row.reported_industry)
        if key not in segment_by_key:
            raise KeyError(
                f"row {row.id}: reported_industry {row.reported_industry!r} "
                "has no entry in the segment map"
            )
        segment_by_row_id[row.id] = segment_by_key[key]
    return segment_by_row_id
