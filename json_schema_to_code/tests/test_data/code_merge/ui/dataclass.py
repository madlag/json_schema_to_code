"""
Base UI Dataclasses

Defines common dataclasses used across all educational activities for UI generation.
These correspond to the schemas defined in action_schema.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

from dataclasses_json import config, dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import (
    ChangeType,
    ObjectType,
)


@dataclass_json
@dataclass(kw_only=True)
class UIStateChangeOperation:
    path: str
    op: ChangeType = field(metadata=config(encoder=lambda x: x.value, decoder=lambda x: ChangeType(x)))
    value_type: list[ObjectType] = field(metadata=config(encoder=lambda xs: [x.value for x in xs], decoder=lambda xs: [ObjectType(x) for x in xs]))
    type: Literal["state_change"] = "state_change"
    value: Optional[Any] = None


@dataclass_json
@dataclass(kw_only=True)
class UIAction:
    """
    Action configuration for user input components.

    Corresponds to Action in action_schema.json.

    An action contains one or more operations that specify what state
    changes to make when a user interacts with an input field (or other operations in the future).
    """

    operations: list[UIActionOperation] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class UIDataCommonFields:
    question: str = field(default="")
    hint: str = field(default="")
    answer: str = field(default="")


# Type aliases from existing code
UIActionOperation = Union[UIStateChangeOperation]


# Module-level functions from existing code
def ui_operation_from_dict(operation_dict: dict[str, Any]) -> UIActionOperation:
    if operation_dict["type"] == "state_change":
        return UIStateChangeOperation.from_dict(operation_dict)
    else:
        raise ValueError(f"Unknown operation type: {operation_dict['type']}")
