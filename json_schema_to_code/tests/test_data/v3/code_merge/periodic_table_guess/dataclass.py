from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.db.app_object_definitions.activities.guess.guess_dataclass import (
    GuessData,
    GuessProblem,
    GuessState,
    GuessUIData,
)


class PeriodicTableType(str, Enum):
    FULL = "Full"
    FIRST_3_ROWS = "First3Rows"


@dataclass_json
@dataclass(kw_only=True)
class ElementProperties:
    atomic_number: int = 0
    column: int = 0
    row: int = 0
    year_discovered: int = 0
    symbol: str = ""
    name: str = ""
    chemical_category: str = ""
    usage: str = ""
    anecdotes: list[str] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableGuessProblem(GuessProblem):
    filter_mode: PeriodicTableType = "Full"
    element_properties: ElementProperties = field(default_factory=lambda: ElementProperties())


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableGuessState(GuessState):
    confirmed_element_properties: list[str] = field(default_factory=list)


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableGuessData(GuessData):
    problem: PeriodicTableGuessProblem = field(default_factory=lambda: PeriodicTableGuessProblem())
    state: PeriodicTableGuessState = field(default_factory=lambda: PeriodicTableGuessState())
    ui_data: PeriodicTableGuessUIData = field(default_factory=lambda: PeriodicTableGuessUIData())


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableGuessUIData(GuessUIData):
    filter_mode: PeriodicTableType = "Full"
    element_states: str = ""
