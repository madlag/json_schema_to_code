"""
Statement Match Pairs Activity Dataclass.

Defines the data structure for match pairs activities applied to statement objects.
The match pairs problem embeds the statement data.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.db.app_object_definitions.activities.match_pairs.match_pairs_dataclass import (
    MatchPairsData,
    MatchPairsProblem,
)
from explayn_dh_agent.barbara.db.app_object_definitions.primitive.statement.statement_dataclass import (
    StatementDataStatement,
)


@dataclass_json
@dataclass(kw_only=True)
class StatementMatchPairsProblem(MatchPairsProblem):
    """
    Match pairs problem containing a statement and match pairs question.

    The statement provides the context being matched.
    """

    statement: StatementDataStatement

    def get_question(self) -> str:
        """Get question text from statement."""
        return self.statement.text


@dataclass_json
@dataclass(kw_only=True)
class StatementMatchPairsData(MatchPairsData):
    """
    Complete activity data for statement match pairs.

    Contains the statement, match pairs, student's state, and UI data.
    """

    problem: StatementMatchPairsProblem
