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
class MatchPair:
    left: MediaContentType
    right: MediaContentType


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsProblem:
    correct_pairs: list[MatchPair]


@dataclass_json
@dataclass(kw_only=True)
class IntegerPair:
    left_index: int
    right_index: int


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsState:
    pairs: list[IntegerPair] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsUIItem:
    index: int
    content: MediaContentType


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsUIRow:
    left: MatchPairsUIItem
    right: MatchPairsUIItem


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsUIData:
    common: UIDataCommonFields = field(default_factory=lambda: UIDataCommonFields())
    rows: list[MatchPairsUIRow] = field(default_factory=list)
    action: UIAction = field(default_factory=lambda: UIAction())


@dataclass_json
@dataclass(kw_only=True)
class MatchPairsData(ActivityState):
    problem: MatchPairsProblem
    state: MatchPairsState = field(default_factory=lambda: MatchPairsState())
    ui_data: MatchPairsUIData = field(default_factory=lambda: MatchPairsUIData())
