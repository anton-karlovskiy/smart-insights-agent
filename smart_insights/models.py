"""Pydantic models: input rows, enriched rows, and every LLM response schema.

The LLM response models (SegmentMapResponse, RowEnrichmentResponse, Insight)
are used as `text_format` with OpenAI strict structured outputs, which demands
all fields required (no defaults) and bans free-form dicts — hence the
variant->segment mapping is a list of pairs, not a dict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter, field_validator


class RawRow(BaseModel):
    """One input row from data/optinmonster_users.json, as-is."""

    id: int
    website_url: str
    reported_industry: str
    opt_in_rate: float
    current_setup_notes: str


class Benchmark(BaseModel):
    """Per-segment stats over clean rows only (stage 4), plus this row's
    up-to-three better-performing peers."""

    website_count: int
    mean_opt_in_rate: float
    median_opt_in_rate: float
    min_opt_in_rate: float
    max_opt_in_rate: float
    canonical_industry_segment: str
    top_performer_ids: list[int]
    # §4.4 thin-segment guard: a non-"other" segment with fewer clean rows
    # than benchmark.MIN_SEGMENT_SIZE is flagged rather than silently trusted.
    low_confidence: bool


class Insight(BaseModel):
    """Stage-5 LLM output. `id` is attached by the pipeline, never requested."""

    recommendation: str
    confidence: Literal["high", "medium", "low"]


class EnrichedRow(RawRow):
    """RawRow plus everything the pipeline adds, keeping originals for
    traceability. Stage-2 fields are committed in data/enriched.json;
    stage 3-5 fields default to their pre-stage values and are stamped
    at runtime."""

    canonical_industry_segment: str
    cleaned_setup_notes: list[str]
    edge_case_anomaly: str | None
    impossible_metric_anomaly: bool = False
    benchmark: Benchmark | None = None
    insight: Insight | None = None

    @property
    def is_anomalous(self) -> bool:
        """Anomalous rows get no benchmark and no insight (SPEC §4.1)."""
        return self.impossible_metric_anomaly or self.edge_case_anomaly is not None

    _blank_anomaly_is_none = field_validator("edge_case_anomaly")(
        lambda v: v if v and v.strip() else None
    )


# --- LLM response schemas (strict structured outputs) ---


class VariantMapping(BaseModel):
    """One reported_industry wording -> canonical segment. Strict schemas
    forbid dict[str, str], so the map travels as a list of pairs."""

    variant: str
    segment: str


class SegmentMapResponse(BaseModel):
    """Stage-2 pass A: the derived canonical segment set and full mapping."""

    segments: list[str]
    mapping: list[VariantMapping]


class RowEnrichmentResponse(BaseModel):
    """Stage-2 pass B: per-row cleaned notes and edge-case judgment."""

    cleaned_setup_notes: list[str]
    edge_case_anomaly: str | None

    # A blank explanation is no explanation: coerce to None so the anomaly
    # gate (is_anomalous) and evaluate's truthiness check can never disagree.
    _blank_anomaly_is_none = field_validator("edge_case_anomaly")(
        lambda v: v if v and v.strip() else None
    )


# --- Stage 1: load & validate, fail loudly on malformed input ---

_RAW_ROW_LIST = TypeAdapter(list[RawRow])
_ENRICHED_ROW_LIST = TypeAdapter(list[EnrichedRow])


def load_raw_rows(path: str | Path) -> list[RawRow]:
    return _RAW_ROW_LIST.validate_json(Path(path).read_text(encoding="utf-8"))


def load_enriched_rows(path: str | Path) -> list[EnrichedRow]:
    return _ENRICHED_ROW_LIST.validate_json(Path(path).read_text(encoding="utf-8"))


def dump_enriched_rows(rows: list[EnrichedRow], path: str | Path) -> None:
    """Write the committed stage-2 artifact. Runtime fields (audit, benchmark,
    insight) are excluded: the artifact records LLM judgment, later stages
    recompute deterministically on every run."""
    stage_2_fields_only = [
        row.model_dump(exclude={"impossible_metric_anomaly", "benchmark", "insight"})
        for row in rows
    ]
    Path(path).write_text(
        json.dumps(stage_2_fields_only, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",  # committed artifact: byte-identical on every OS
    )
