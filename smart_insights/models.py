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

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from smart_insights.text import normalize_ascii


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
    # Thin-segment guard: a non-"other" segment with fewer clean rows
    # than benchmark.MIN_SEGMENT_SIZE is flagged rather than silently trusted.
    low_confidence: bool


# A model's docstring and its Field descriptions both travel to the API inside
# the JSON schema, so both are prompt surface: keep them short, and keep them
# restating the instructions rather than adding rules of their own. Field-level
# constraints belong here, beside the field, per OpenAI's structured-outputs
# guide; the task and its reasoning stay in the system prompt.
class Insight(BaseModel):
    """Stage-5 LLM output: the single next best action for one website."""

    recommendation: str = Field(
        description=(
            "The single next best action for this site, in plain English for its "
            "owner. Under 500 characters. Every number in it must appear in the "
            "facts provided; never compute or invent one. Exactly one action."
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "How strongly the facts support the recommendation. 'high' only when "
            "the segment is a real peer group (benchmark.low_confidence is false) "
            "and the top performers agree with one another; 'low' when the facts "
            "cannot carry weight (low_confidence true, a segment of one, or notes "
            "too thin to ground the action)."
        )
    )

    # The prompt asks for plain ASCII; this enforces it, so a stray curly quote
    # never reaches the committed output or the cp1252 console.
    _recommendation_ascii = field_validator("recommendation")(normalize_ascii)


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
        """Anomalous rows get no benchmark and no insight (the anomaly invariant)."""
        return self.impossible_metric_anomaly or self.edge_case_anomaly is not None

    _blank_anomaly_is_none = field_validator("edge_case_anomaly")(
        lambda v: v if v and v.strip() else None
    )


# --- LLM response schemas (strict structured outputs) ---


class VariantMapping(BaseModel):
    """One reported_industry wording -> canonical segment. Strict schemas
    forbid dict[str, str], so the map travels as a list of pairs."""

    variant: str = Field(
        description="One input reported_industry wording, spelled exactly as given."
    )
    segment: str = Field(description="The canonical segment it belongs to; must be in `segments`.")


class SegmentMapResponse(BaseModel):
    """Stage-2 pass A: the derived canonical segment set and full mapping."""

    segments: list[str] = Field(
        description=(
            "The canonical industry segments, snake_case. Each is a benchmarking peer "
            "group, so prefer a segment that gathers at least three websites over a "
            "finer one that cannot be benchmarked."
        )
    )
    mapping: list[VariantMapping] = Field(
        description="Every input wording, exactly once, mapped onto one segment."
    )


class RowEnrichmentResponse(BaseModel):
    """Stage-2 pass B: per-row cleaned notes and edge-case judgment."""

    cleaned_setup_notes: list[str] = Field(
        description=(
            "current_setup_notes split into individual conversion-setup notes, typos and "
            "grammar fixed, meaning and concrete details preserved, off-topic remarks "
            "dropped. Nothing added. Empty when the note describes no setup at all."
        )
    )
    edge_case_anomaly: str | None = Field(
        description=(
            "One sentence naming the problem when the record's own contents show the "
            "opt_in_rate is not a trustworthy measure of opt-in performance, or the record "
            "contradicts itself. Null when the record is internally consistent. An "
            "opt_in_rate outside 0-100 is caught elsewhere and is not, by itself, an "
            "edge case."
        )
    )

    # Both prose fields are asked for in plain ASCII; enforce it deterministically.
    _notes_ascii = field_validator("cleaned_setup_notes")(
        lambda v: [normalize_ascii(note) for note in v]
    )

    # A blank explanation is no explanation: coerce to None so the anomaly
    # gate (is_anomalous) and evaluate's truthiness check can never disagree.
    _blank_anomaly_is_none = field_validator("edge_case_anomaly")(
        lambda v: normalize_ascii(v) if v and v.strip() else None
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
