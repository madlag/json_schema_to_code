from __future__ import annotations

from dataclasses import dataclass, field

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState
from explayn_dh_agent.barbara.db.app_object_definitions.activities.media_content.media_content_types_dataclass import (
    MediaContentType,
)
from explayn_dh_agent.barbara.db.app_object_definitions.activities.ui_dataclass import (
    UIAction,
    UIDataCommonFields,
)


@dataclass_json
@dataclass(kw_only=True)
class QuizAnswer:
    content: MediaContentType
    is_correct: bool


@dataclass_json
@dataclass(kw_only=True)
class QuizProblem:
    answers: list[QuizAnswer]


@dataclass_json
@dataclass(kw_only=True)
class QuizState:
    selected_answers: list[int] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class QuizUIAnswerOption:
    answer: QuizAnswer
    is_selected: bool = False
    action: UIAction = field(default_factory=lambda: UIAction())


@dataclass_json
@dataclass(kw_only=True)
class QuizUIData:
    common: UIDataCommonFields = field(default_factory=lambda: UIDataCommonFields())
    answers: list[QuizUIAnswerOption] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class QuizData(ActivityState):
    problem: QuizProblem
    state: QuizState = field(default_factory=lambda: QuizState())
    ui_data: QuizUIData = field(default_factory=lambda: QuizUIData())
