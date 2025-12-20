"""
Dataclasses for periodic table activity states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableData(ActivityState):
    periodic_table: PeriodicTableDataPeriodicTable
    type: Literal["chemistry/periodic_table"] = "chemistry/periodic_table"


@dataclass_json
@dataclass(kw_only=True)
class Elements:
    atomic_number: int
    symbol: str
    name: str
    atomic_mass: float
    group: int
    period: int
    block: str
    category: str
    electron_configuration: str
    electronegativity: float
    oxidation_states: list[int]
    melting_point: float
    boiling_point: float
    density: float
    phase_at_stp: str
    discovered_by: str
    discovery_year: int
    radioactive: bool


@dataclass_json
@dataclass(kw_only=True)
class PeriodicTableDataPeriodicTable:
    elements: list[Elements]
