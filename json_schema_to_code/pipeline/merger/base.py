"""
Base classes for AST merging.

Provides the abstract interface for language-specific mergers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

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
    """Container for extracted custom code from an existing file.

    Attributes:
        custom_imports: Import statements not in the generated code
        constants: Module-level constant assignments
        custom_classes: Full class definitions not in generated code (e.g., Enums)
        class_methods: Dict mapping class name to list of custom method names
        class_attributes: Dict mapping class name to list of custom attribute names
        post_init_bodies: Dict mapping class name to custom __post_init__ body lines
        raw_sections: Raw code sections marked for preservation (e.g., // CUSTOM CODE)
        class_docstrings: Dict mapping class name to docstring content
        method_docstrings: Dict mapping (class_name, method_name) to docstring content
        module_docstring: Module-level docstring content
    """

    custom_imports: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)
    custom_classes: list[str] = field(default_factory=list)
    class_methods: dict[str, list[str]] = field(default_factory=dict)
    class_attributes: dict[str, list[str]] = field(default_factory=dict)
    post_init_bodies: dict[str, list[str]] = field(default_factory=dict)
    raw_sections: list[str] = field(default_factory=list)
    class_docstrings: dict[str, str] = field(default_factory=dict)
    method_docstrings: dict[tuple[str, str], str] = field(default_factory=dict)
    module_docstring: str | None = None

    def is_empty(self) -> bool:
        """Check if there's any custom code to preserve."""
        return (
            not self.custom_imports
            and not self.constants
            and not self.custom_classes
            and not self.class_methods
            and not self.class_attributes
            and not self.post_init_bodies
            and not self.raw_sections
            and not self.class_docstrings
            and not self.method_docstrings
            and self.module_docstring is None
        )


class AstMerger(ABC):
    """Abstract base class for language-specific AST mergers.

    Subclasses implement the language-specific logic for:
    1. Parsing existing code into an AST
    2. Extracting custom code elements
    3. Merging custom code into generated AST
    4. Validating the merged result
    """

    @abstractmethod
    def parse(self, code: str) -> Any:
        """Parse source code into an AST.

        Args:
            code: Source code string

        Returns:
            Language-specific AST representation

        Raises:
            CodeMergeError: If the code cannot be parsed
        """
        pass

    @abstractmethod
    def extract_custom_code(self, existing_code: str, generated_code: str) -> CustomCode:
        """Extract custom code elements from existing file.

        Compares existing code with generated code to identify
        elements that were added by the user and should be preserved.

        Args:
            existing_code: The existing file contents
            generated_code: The newly generated code

        Returns:
            CustomCode object containing extracted elements

        Raises:
            CodeMergeError: If existing code cannot be parsed
        """
        pass

    @abstractmethod
    def merge(self, generated_code: str, custom_code: CustomCode) -> str:
        """Merge custom code into generated code.

        Args:
            generated_code: The newly generated code
            custom_code: Custom code elements to preserve

        Returns:
            Merged code string

        Raises:
            CodeMergeError: If merge fails or would lose custom code
        """
        pass

    @abstractmethod
    def validate(self, code: str) -> None:
        """Validate that merged code is syntactically correct.

        Args:
            code: The merged code to validate

        Raises:
            CodeMergeError: If validation fails
        """
        pass

    def merge_files(
        self,
        generated_code: str,
        existing_code: str,
        merge_strategy: MergeStrategy = MergeStrategy.ERROR,
    ) -> str:
        """High-level merge operation.

        Convenience method that performs the full merge workflow:
        1. Extract custom code from existing file
        2. Merge into generated code
        3. Validate result

        Args:
            generated_code: The newly generated code
            existing_code: The existing file contents
            merge_strategy: How to handle existing value members not in generated code

        Returns:
            Merged code string

        Raises:
            CodeMergeError: If any step fails
        """
        custom_code = self.extract_custom_code(existing_code, generated_code)

        if custom_code.is_empty():
            # No custom code to preserve, just return generated
            return generated_code

        merged = self.merge(generated_code, custom_code)
        self.validate(merged)

        return merged
