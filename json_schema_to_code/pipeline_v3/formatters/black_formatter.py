"""
Black formatter for Python code.
"""

from __future__ import annotations

from ..config import FormatterConfig
from .base import Formatter


class BlackFormatter(Formatter):
    """Formatter using black for Python code."""

    def __init__(self):
        self._black = None
        self._available = None

    def is_available(self) -> bool:
        """Check if black is installed."""
        if self._available is None:
            try:
                import black

                self._black = black
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def format(self, code: str, config: FormatterConfig) -> str:
        """
        Format Python code using black.

        Args:
            code: Python source code to format
            config: Formatter configuration

        Returns:
            Formatted code
        """
        if not self.is_available():
            # Return unformatted code if black is not available
            return code

        black = self._black

        # Parse target version
        target_versions = set()
        if config.target_version:
            version_map = {
                "py38": black.TargetVersion.PY38,
                "py39": black.TargetVersion.PY39,
                "py310": black.TargetVersion.PY310,
                "py311": black.TargetVersion.PY311,
                "py312": black.TargetVersion.PY312,
            }
            # Also handle "py313" even if black doesn't have it yet
            if config.target_version in version_map:
                target_versions.add(version_map[config.target_version])
            elif config.target_version == "py313":
                # Use PY312 as fallback for PY313
                if hasattr(black.TargetVersion, "PY313"):
                    target_versions.add(black.TargetVersion.PY313)
                else:
                    target_versions.add(black.TargetVersion.PY312)

        # Create mode
        mode = black.Mode(
            target_versions=target_versions,
            line_length=config.line_length,
            string_normalization=config.string_normalization,
            magic_trailing_comma=config.magic_trailing_comma,
        )

        try:
            formatted = black.format_str(code, mode=mode)
            return formatted
        except black.InvalidInput:
            # If formatting fails, return original code
            return code


def format_with_black(
    code: str,
    line_length: int = 100,
    target_version: str = "py312",
) -> str:
    """
    Convenience function to format Python code with black.

    Args:
        code: Python source code
        line_length: Maximum line length
        target_version: Python version target (e.g., "py312")

    Returns:
        Formatted code
    """
    formatter = BlackFormatter()
    config = FormatterConfig(
        enabled=True,
        line_length=line_length,
        target_version=target_version,
    )
    return formatter.format(code, config)
