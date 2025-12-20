"""
Base class for AST-based code generation backends.

Defines the interface that all language-specific AST backends must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..analyzer.ir_nodes import IR, TypeRef
from ..config import CodeGeneratorConfig


class AstBackend(ABC):
    """Abstract base class for AST-based code generation backends."""

    # Type mapping from schema types to language types
    TYPE_MAP: dict[str, str] = {}

    # File extension
    FILE_EXTENSION: str = ""

    def __init__(self, config: CodeGeneratorConfig):
        """
        Initialize the backend.

        Args:
            config: Code generation configuration
        """
        self.config = config

    @abstractmethod
    def generate(self, ir: IR) -> str:
        """
        Generate code from IR.

        Args:
            ir: The intermediate representation

        Returns:
            Generated code as a string
        """

    @abstractmethod
    def translate_type(self, type_ref: TypeRef) -> str:
        """
        Translate an IR type to a language-specific type string.

        Args:
            type_ref: The type reference

        Returns:
            Language-specific type string
        """

    @abstractmethod
    def format_default_value(self, value: Any, type_ref: TypeRef) -> str:
        """
        Format a default value for the target language.

        Args:
            value: The default value
            type_ref: The type of the value

        Returns:
            Formatted default value string
        """

    def _snake_to_pascal(self, text: str) -> str:
        """Convert snake_case to PascalCase."""
        import re

        words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text.replace("_", " ").replace("-", " "))
        return "".join(word.capitalize() for word in words if word)

    def _get_comment_prefix(self) -> str:
        """Get the comment prefix for the language."""
        return "#" if self.FILE_EXTENSION == "py" else "//"
