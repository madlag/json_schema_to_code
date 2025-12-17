from __future__ import annotations

from dataclasses import dataclass, field

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState
from explayn_dh_agent.barbara.db.app_object_definitions.activities.ui_dataclass import (
    UIAction,
    UIDataCommonFields,
)


@dataclass_json
@dataclass(kw_only=True)
class TrueFalseProblem:
    correct_answer: bool


@dataclass_json
@dataclass(kw_only=True)
class TrueFalseState:
    selected_answer: bool | None = None


@dataclass_json
@dataclass(kw_only=True)
class TrueFalseUIAnswerOption:
    value: bool
    text: str = ""
    is_correct: bool = False
    is_selected: bool = False
    action: UIAction = field(default_factory=lambda: UIAction())


@dataclass_json
@dataclass(kw_only=True)
class TrueFalseUIData:
    common: UIDataCommonFields = field(default_factory=lambda: UIDataCommonFields())
    answers: list[TrueFalseUIAnswerOption] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class TrueFalseData(ActivityState):
    problem: TrueFalseProblem
    state: TrueFalseState = field(default_factory=lambda: TrueFalseState())
    ui_data: TrueFalseUIData = field(default_factory=lambda: TrueFalseUIData())
