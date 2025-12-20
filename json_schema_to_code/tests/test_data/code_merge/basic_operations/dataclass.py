#!/usr/bin/env python3
"""
UI Data Classes for Basic Math Operations

Defines common dataclasses used across all basic math operations
(addition, subtraction, multiplication, division) for columnar display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.db.app_object_definitions.activities.ui_dataclass import (
    UIAction,
)


class ColorFlag(str, Enum):
    """Color flag for visual feedback on digits."""

    NORMAL = "normal"
    HIGHLIGHT = "highlight"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"


class InteractionType(str, Enum):
    """Interaction type for digit display."""

    READ_ONLY = "ReadOnly"
    EDITABLE = "Editable"
    PLACEHOLDER = "Placeholder"


@dataclass_json
@dataclass
class DigitState:
    """State for a single digit display (can be label or input)."""

    text: str
    color_flag: ColorFlag = ColorFlag.NORMAL
    interaction: InteractionType = InteractionType.READ_ONLY
    action: Optional[UIAction] = None


@dataclass_json
@dataclass
class OperandRowState:
    """State for one operand row (a number in the operation)."""

    digits: list[DigitState] = field(default_factory=list)


@dataclass_json
@dataclass
class InputRowState:
    """State for an input row (carry-over or result)."""

    digits: list[DigitState] = field(default_factory=list)
