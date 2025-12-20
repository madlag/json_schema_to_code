"""
Statement Quiz Activity Dataclass.

Defines the data structure for quiz activities applied to statement objects.
The quiz problem embeds the statement data.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.db.app_object_definitions.activities.quiz.quiz_dataclass import (
    QuizData,
    QuizProblem,
)
from explayn_dh_agent.barbara.db.app_object_definitions.primitive.statement.statement_dataclass import (
    StatementDataStatement,
)


@dataclass_json
@dataclass(kw_only=True)
class StatementQuizProblem(QuizProblem):
    """
    Quiz problem containing a statement and quiz question/answers.

    The statement provides the content being quizzed about.
    """

    statement: StatementDataStatement

    def __post_init__(self):
        self.question_text = self.statement.text


@dataclass_json
@dataclass(kw_only=True)
class StatementQuizData(QuizData):
    """
    Complete activity data for statement quiz.

    Contains the statement, quiz question/answers, student's state, and UI data.
    """

    problem: StatementQuizProblem
