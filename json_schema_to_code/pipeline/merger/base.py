"""
Base classes for AST merging.

Provides the abstract interface for language-specific mergers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import MergeStrategy


class CodeMergeError(Exception):
    """Raised when code merging fails.

    This can happen when:
    - The existing file cannot be parsed
    - Merge would lose custom code (class removed, etc.)
    - Validation fails after merge
    - Structural incompatibility is detected
    """

    pass


@dataclass
class CustomCode:
    """Hand-written code found in an existing C# / Swift file, to carry into the regenerated one.

    Attributes:
        custom_imports: Import / using statements the generator does not emit
        custom_classes: Whole top-level declarations the generator does not produce
        class_methods: Class name -> custom member declarations (methods, constructors)
        class_attributes: Class name -> custom property declarations
        raw_sections: Bodies of ``// CUSTOM CODE START/END`` blocks
        member_leading_comments: Class name -> member key -> comment lines above it
    """

    custom_imports: list[str] = field(default_factory=list)
    custom_classes: list[str] = field(default_factory=list)
    class_methods: dict[str, list[str]] = field(default_factory=dict)
    class_attributes: dict[str, list[str]] = field(default_factory=dict)
    raw_sections: list[str] = field(default_factory=list)
    member_leading_comments: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if there's any custom code to preserve."""
        return not (self.custom_imports or self.custom_classes or self.class_methods or self.class_attributes or self.raw_sections or self.member_leading_comments)


class AstMerger(ABC):
    """A language's merge of freshly generated code into an existing file.

    ``merge_files`` is the single entry point; how a merger gets there -- Python walks
    the existing module's AST, C# and Swift extract custom code with tree-sitter and
    splice it back -- is its own business.
    """

    @abstractmethod
    def merge_files(
        self,
        generated_code: str,
        existing_code: str,
        merge_strategy: MergeStrategy = MergeStrategy.ERROR,
    ) -> str:
        """Merge ``generated_code`` into ``existing_code``, keeping the hand-written parts.

        Args:
            generated_code: The newly generated code
            existing_code: The existing file contents
            merge_strategy: How to handle existing value members not in generated code

        Returns:
            Merged code string

        Raises:
            CodeMergeError: If the existing file cannot be parsed, the merge would lose
                custom code, or the result does not validate
        """

    @abstractmethod
    def validate(self, code: str) -> None:
        """Raise CodeMergeError unless ``code`` is syntactically sound merged output."""
