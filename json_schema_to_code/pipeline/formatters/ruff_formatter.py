"""
Ruff formatter for Python code.
"""

from __future__ import annotations

import subprocess

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

    def format(self, code: str, config: FormatterConfig, path: str | None = None) -> str:
        """
        Format Python code using ruff.

        Args:
            code: Python source code to format
            config: Formatter configuration
            path: Destination path of the generated file, when known. Passed to ruff as
                --stdin-filename so ruff resolves the *consuming* project's settings
                (notably isort's known-first-party) instead of this package's.

        Returns:
            Formatted code
        """
        if not self.is_available():
            # Return unformatted code if ruff is not available
            return code

        stdin_filename = path or "code.py"

        if config.sort_imports:
            code = self._sort_imports(code, config, stdin_filename)

        cmd = ["ruff", "format", "--stdin-filename", stdin_filename]

        if config.line_length:
            cmd.extend(["--line-length", str(config.line_length)])

        if config.target_version:
            cmd.extend(["--target-version", config.target_version])

        return self._run(cmd, code)

    def _sort_imports(self, code: str, config: FormatterConfig, stdin_filename: str) -> str:
        """Apply ruff's isort rules (I) only.

        The backend already emits imports sorted and grouped, but it cannot know which
        modules are first-party to the project consuming the generated file, so it cannot
        place the blank lines isort puts between groups. ruff can, from that project's own
        configuration -- which is why the destination path matters here.
        """
        cmd = ["ruff", "check", "--select", "I", "--fix-only", "--stdin-filename", stdin_filename, "-"]
        if config.line_length:
            cmd.extend(["--line-length", str(config.line_length)])
        return self._run(cmd, code)

    def _run(self, cmd: list[str], code: str) -> str:
        """Run a ruff command over ``code`` via stdin, returning it unchanged on any failure."""
        try:
            result = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=30)
        except subprocess.SubprocessError:
            return code
        # ruff check --fix-only exits non-zero only on real errors; both commands print the
        # resulting source on success. Anything else: keep the input rather than lose it.
        if result.returncode != 0 or not result.stdout:
            return code
        return result.stdout


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
