"""Versioned presentation contracts shared by the Agent and deterministic renderer."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .models import (
    CoverSlide,
    DecisionsActionsSlide,
    DeckPlan,
    MeetingAnalysis,
    MindMapSlide,
    NextStepsSlide,
    OverviewSlide,
    TopicsSlide,
)

SLIDE_ORDER = (
    "cover",
    "overview",
    "topics",
    "decisions_actions",
    "mind_map",
    "next_steps",
)


class DeckLimits(BaseModel):
    """Cardinality and clipping limits for the six-slide template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topics: int = Field(ge=1, le=6)
    decisions: int = Field(ge=1, le=10)
    actions: int = Field(ge=1, le=10)
    questions: int = Field(ge=1, le=10)
    title_display_width: int = Field(ge=20)
    subtitle_display_width: int = Field(ge=40)
    topic_display_width: int = Field(ge=20)
    list_item_display_width: int = Field(ge=40)
    next_step_display_width: int = Field(ge=40)


class EmptyStates(BaseModel):
    """Presentation-safe text used only when evidence-backed content is absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decisions: str = Field(min_length=1)
    actions: str = Field(min_length=1)
    questions: str = Field(min_length=1)
    next_step: str = Field(min_length=1)


class DeckContract(BaseModel):
    """Versioned contract that bridges DeckPlan and the packaged PPTX template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    slide_order: tuple[str, ...]
    limits: DeckLimits
    empty_states: EmptyStates


class FontSizes(BaseModel):
    """Named font sizes consumed by the renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cover_title: int = Field(gt=0)
    cover_subtitle: int = Field(gt=0)
    summary: int = Field(gt=0)
    metric: int = Field(gt=0)
    topic: int = Field(gt=0)
    decision: int = Field(gt=0)
    action_number: int = Field(gt=0)
    action_content: int = Field(gt=0)
    action_metadata: int = Field(gt=0)
    question: int = Field(gt=0)
    next_step: int = Field(gt=0)


class PresentationColors(BaseModel):
    """Named RGB colors consumed by the renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_text: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    secondary_text: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    inverse_text: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    topic_accent: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    decision_accent: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    action_accent: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")


class PresentationSpacing(BaseModel):
    """Named paragraph spacing values consumed by the renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numbered_list_after: int = Field(ge=0)
    action_after: int = Field(ge=0)


class MindMapStyle(BaseModel):
    """Mind-map image placement inside the template frame."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_margin_inches: float = Field(ge=0, le=1)


class PresentationStyle(BaseModel):
    """Versioned visual tokens used by the deterministic PowerPoint renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    font_family: str = Field(min_length=1)
    font_sizes: FontSizes
    colors: PresentationColors
    spacing_points: PresentationSpacing
    mind_map: MindMapStyle


@lru_cache(maxsize=1)
def load_deck_contract() -> DeckContract:
    """Load and validate the packaged six-slide content contract."""
    value = _load_yaml_resource("deck-contract.yaml")
    contract = DeckContract.model_validate(value)
    if contract.slide_order != SLIDE_ORDER:
        raise ValueError("Presentation deck contract must preserve the six-slide order")
    return contract


@lru_cache(maxsize=1)
def load_presentation_style() -> PresentationStyle:
    """Load and validate the packaged visual style tokens."""
    return PresentationStyle.model_validate(
        _load_yaml_resource("presentation-style.yaml")
    )


def resolve_deck_plan(
    analysis: MeetingAnalysis,
    contract: DeckContract | None = None,
) -> DeckPlan:
    """Return the Agent-authored DeckPlan or a deterministic legacy-v6 fallback."""
    if analysis.deck_plan is not None:
        return analysis.deck_plan
    active = contract or load_deck_contract()
    limits = active.limits
    questions = analysis.open_questions[: limits.questions]
    return DeckPlan(
        cover=CoverSlide(title=analysis.title, subtitle=analysis.summary),
        overview=OverviewSlide(summary=analysis.summary),
        topics=TopicsSlide(items=analysis.topics[: limits.topics]),
        decisions_actions=DecisionsActionsSlide(
            decisions=analysis.decisions[: limits.decisions],
            actions=analysis.action_items[: limits.actions],
        ),
        mind_map=MindMapSlide(title=analysis.mind_map.label),
        next_steps=NextStepsSlide(
            questions=questions,
            next_step=questions[0] if questions else None,
        ),
    )


def ensure_deck_plan(analysis: MeetingAnalysis) -> MeetingAnalysis:
    """Attach a deterministic fallback DeckPlan when the active Agent omits it."""
    if analysis.deck_plan is not None:
        return analysis
    return analysis.model_copy(update={"deck_plan": resolve_deck_plan(analysis)})


def _load_yaml_resource(name: str) -> object:
    resource = files("meeting_agent").joinpath(
        "skills", "presentation-story", name
    )
    value = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Presentation resource {name} must contain a YAML object")
    return value
