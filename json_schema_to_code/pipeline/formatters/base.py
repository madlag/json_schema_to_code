"""
Base class for code formatters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import FormatterConfig


class Formatter(ABC):
    """Abstract base class for code formatters."""

    @abstractmethod
    def format(self, code: str, config: FormatterConfig, path: str | None = None) -> str:
        """
        Format the given code.

        Args:
            code: The source code to format
            config: Formatter configuration
            path: Destination path of the generated file, when known. Formatters that
                shell out to a project-aware tool use it to resolve that project's
                configuration (e.g. isort's known-first-party).

        Returns:
            Formatted code
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the formatter is available (dependencies installed).

        Returns:
            True if the formatter can be used
        """
