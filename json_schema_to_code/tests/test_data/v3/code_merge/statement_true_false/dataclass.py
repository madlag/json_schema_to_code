from __future__ import annotations

from dataclasses import dataclass

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.db.app_object_definitions.activities.true_false.true_false_dataclass import (
    TrueFalseData,
    TrueFalseProblem,
)
from explayn_dh_agent.barbara.db.app_object_definitions.primitive.statement.statement_dataclass import (
    StatementDataStatement,
)


@dataclass_json
@dataclass(kw_only=True)
class StatementTrueFalseProblem(TrueFalseProblem):
    """
    True/false problem about a statement. The statement.text is the question.
    """

    statement: StatementDataStatement

    def get_question(self) -> str:
        """Get question text from statement."""
        return self.statement.text


@dataclass_json
@dataclass(kw_only=True)
class StatementTrueFalseData(TrueFalseData):
    """
    Complete activity data for statement true/false.
    """

    problem: StatementTrueFalseProblem
