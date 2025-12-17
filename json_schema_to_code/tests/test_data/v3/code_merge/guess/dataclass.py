"""
Data classes for Guess activity.

This module defines the generic dataclasses representing the problem and state
for guess-type educational activities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState
from explayn_dh_agent.barbara.db.app_object_definitions.activities.ui_dataclass import (
    UIAction,
)


class GuessItemState(str, Enum):
    """
    State of an item in the guess activity UI.
    """

    NORMAL = "N"
    HIDDEN = "H"
    CORRECT = "C"
    INCORRECT = "I"
    FILTERED = "F"
    FILTERED_BY_USER = "U"
    FILTERED_BY_AGENT = "A"


@dataclass_json
@dataclass(kw_only=True)
class GuessHint:
    """
    A hint for the guess activity.
    """

    hint_id: str = ""
    hint_text: str = ""
    difficulty: int = 0


@dataclass_json
@dataclass(kw_only=True)
class GuessProblem:
    """
    Generic guess problem definition.
    """

    correct_item_id: int = 0
    question_text: str = ""
    difficulty_level: int = 1
    correct_answer_text: str = ""
    hints: list[GuessHint] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class GuessState:
    """
    State tracking for guess activity.
    """

    selected_item_ids: list[int] = field(default_factory=list)
    item_states: str = ""
    used_hints: list[str] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class GuessUIData:
    """
    Complete UI state for the guess activity view.
    """

    question_text: str = ""
    used_hints: list[str] = field(default_factory=list)
    item_states: str = ""
    actionTemplate: UIAction = field(default_factory=lambda: UIAction(operations=[]))


@dataclass_json
@dataclass(kw_only=True)
class GuessData(ActivityState):
    """
    Complete activity data for guess activity.

    This dataclass represents the entire state of a guess activity,
    including the problem definition and current student progress.
    """

    problem: GuessProblem = field(default_factory=lambda: GuessProblem())
    state: GuessState = field(default_factory=lambda: GuessState())
    ui_data: GuessUIData = field(default_factory=lambda: GuessUIData())
