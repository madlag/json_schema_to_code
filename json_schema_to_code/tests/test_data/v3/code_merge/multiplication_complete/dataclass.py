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
MULTIPLICAND = "multiplicand"
MULTIPLIER = "multiplier"
STATE = "state"
PARTIAL_PRODUCTS = "partial_products"
CARRY_ROWS = "carry_rows"
FINAL_SUM = "final_sum"
FINAL_CARRY_ROW = "final_carry_row"


@dataclass_json
@dataclass(kw_only=True)
class MultiplicationCompleteProblem:
    multiplicand: int = 0
    multiplier: int = 0


@dataclass_json
@dataclass(kw_only=True)
class MultiplicationCompleteState:
    partial_products: list[list[None | int]] = field(default_factory=list)
    carry_rows: list[list[None | int]] = field(default_factory=list)
    final_sum: list[None | int] = field(default_factory=list)
    final_carry_row: list[None | int] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class MultiplicationCompleteUIData:
    """
    Complete UI state for the multiplication activity view.
    Built by the agent/backend and consumed by the Unity view.
    """

    question_text: str = ""
    multiplicand_row: OperandRowState = field(default_factory=lambda: OperandRowState())
    multiplier_row: OperandRowState = field(default_factory=lambda: OperandRowState())
    partial_product_carry_rows: list[InputRowState] = field(default_factory=list)
    partial_product_rows: list[InputRowState] = field(default_factory=list)
    final_carry_row: InputRowState = field(default_factory=lambda: InputRowState())
    final_sum_row: InputRowState = field(default_factory=lambda: InputRowState())


@dataclass_json
@dataclass(kw_only=True)
class MultiplicationCompleteData(ActivityState):
    problem: MultiplicationCompleteProblem
    state: MultiplicationCompleteState = field(default_factory=lambda: MultiplicationCompleteState())
    ui_data: MultiplicationCompleteUIData = field(default_factory=lambda: MultiplicationCompleteUIData())
