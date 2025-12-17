from __future__ import annotations

from dataclasses import dataclass, field

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState
from explayn_dh_agent.barbara.db.app_object_definitions.maths.basic_operations.activities.complete.basic_operations_dataclass import (
    InputRowState,
    OperandRowState,
)

# Field constants from existing code
PROBLEM = "problem"
OPERANDS = "operands"
STATE = "state"
CARRY_OVER_ROW = "carry_over_row"
RESULT_ROW = "result_row"


@dataclass_json
@dataclass(kw_only=True)
class AdditionCompleteProblem:
    operands: list[int] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class AdditionCompleteState:
    carry_over_row: list[None | int] = field(default_factory=list)
    result_row: list[None | int] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class AdditionCompleteUIData:
    """
    Complete UI state for the addition activity view.
    Built by the agent/backend and consumed by the Unity view.
    """

    question_text: str = ""
    operand_rows: list[OperandRowState] = field(default_factory=list)
    carry_over_row: InputRowState = field(default_factory=lambda: InputRowState())
    result_row: InputRowState = field(default_factory=lambda: InputRowState())


@dataclass_json
@dataclass(kw_only=True)
class AdditionCompleteData(ActivityState):
    problem: AdditionCompleteProblem
    state: AdditionCompleteState = field(default_factory=lambda: AdditionCompleteState())
    ui_data: AdditionCompleteUIData = field(default_factory=lambda: AdditionCompleteUIData())
