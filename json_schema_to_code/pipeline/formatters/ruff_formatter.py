"""
Ruff formatter for Python code.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..config import FormatterConfig
from .base import Formatter


class RuffFormatter(Formatter):
    """Formatter using ruff for Python code."""

    def __init__(self):
        self._available = None

    def is_available(self) -> bool:
        """Check if ruff is installed."""
        if self._available is None:
            try:
                result = subprocess.run(
                    ["ruff", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._available = False
        return self._available

    def format(self, code: str, config: FormatterConfig) -> str:
        """
        Format Python code using ruff.

        Args:
            code: Python source code to format
            config: Formatter configuration

        Returns:
            Formatted code
        """
        if not self.is_available():
            # Return unformatted code if ruff is not available
            return code

        # Write code to a temporary file (ruff format works on files)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = Path(f.name)

        try:
            # Build ruff format command
            cmd = ["ruff", "format", "--stdin-filename", "code.py"]

            if config.line_length:
                cmd.extend(["--line-length", str(config.line_length)])

            if config.target_version:
                cmd.extend(["--target-version", config.target_version])

            # Run ruff format via stdin/stdout
            result = subprocess.run(
                cmd,
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return result.stdout
            else:
                # If formatting fails, return original code
                return code
        except subprocess.SubprocessError:
            return code
        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)


def format_with_ruff(
    code: str,
    line_length: int = 100,
    target_version: str = "py312",
) -> str:
    """
    Convenience function to format Python code with ruff.

    Args:
        code: Python source code
        line_length: Maximum line length
        target_version: Python version target (e.g., "py312")

    Returns:
        Formatted code
    """
    formatter = RuffFormatter()
    config = FormatterConfig(
        enabled=True,
        line_length=line_length,
        target_version=target_version,
    )
    return formatter.format(code, config)
