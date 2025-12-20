from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(kw_only=True)
class StatementDataStatement:
    text: str


@dataclass_json
@dataclass(kw_only=True)
class StatementData:
    statement: StatementDataStatement
    type: Literal["primitive/statement"] = "primitive/statement"
