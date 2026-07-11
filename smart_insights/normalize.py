"""Industry normalization: pure Python around the one LLM derivation call.

Collect (here) -> derive (LLM, in preprocess.py) -> validate + apply (here).
The canonical segment set is derived from `reported_industry` ALONE — no other
field is consulted; contradictions belong in `edge_case_anomaly`, never here.

Scaling note: the dedupe already keeps the derive call cheap (token cost
scales with distinct wordings, not row count), but past a few thousand
distinct variants, chunk the list and move it, with the per-row stage-2
calls, to the Batch API. Out of scope for this prototype (SPEC §10).
"""

from __future__ import annotations

from smart_insights.models import RawRow, SegmentMapResponse


def _fold(value: str) -> str:
    """Dedupe/lookup key: case-folded, whitespace-collapsed."""
    return " ".join(value.split()).casefold()


def collect_variants(rows: list[RawRow]) -> list[str]:
    """Unique reported_industry wordings, first-seen spelling kept,
    deduped case- and whitespace-insensitively. Deterministic order."""
    seen: dict[str, str] = {}
    for row in rows:
        key = _fold(row.reported_industry)
        if key not in seen:
            seen[key] = row.reported_industry.strip()
    return sorted(seen.values(), key=_fold)


def validate_segment_map(
    variants: list[str], response: SegmentMapResponse
) -> dict[str, str]:
    """Check the LLM's map covers every variant and invents no segment;
    return it as a plain variant->segment dict. Raises ValueError with every
    problem listed, so a retry prompt can carry the full error."""
    mapping = {pair.variant: pair.segment for pair in response.mapping}
    segments = set(response.segments)
    folded_keys = {_fold(k): v for k, v in mapping.items()}

    problems: list[str] = []
    for variant in variants:
        if _fold(variant) not in folded_keys:
            problems.append(f"variant {variant!r} is missing from the mapping")
    for variant, segment in mapping.items():
        if segment not in segments:
            problems.append(
                f"variant {variant!r} maps to {segment!r}, which is not in segments"
            )
    if problems:
        raise ValueError("; ".join(problems))
    return mapping


def apply_segment_map(rows: list[RawRow], mapping: dict[str, str]) -> dict[int, str]:
    """Stamp every row's canonical segment by plain dict lookup (folded key).
    Returns row id -> segment. Every row gets a segment, anomalous ones
    included. Raises KeyError if a row's wording is not covered."""
    folded = {_fold(k): v for k, v in mapping.items()}
    result: dict[int, str] = {}
    for row in rows:
        key = _fold(row.reported_industry)
        if key not in folded:
            raise KeyError(
                f"row {row.id}: reported_industry {row.reported_industry!r} "
                "has no entry in the segment map"
            )
        result[row.id] = folded[key]
    return result
