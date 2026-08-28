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
                --stdin-filename so ruff resolves the *consuming* project's settings --
                isort's known-first-party, the line length -- instead of this package's.
                Without it, ``config.line_length`` stands in for the project's.

        Returns:
            Formatted code
        """
        if not self.is_available():
            # Return unformatted code if ruff is not available
            return code

        stdin_filename = path or "code.py"
        # The consuming project's configuration decides the line length; only a
        # destination-less call has no project to defer to.
        line_length = [] if path or not config.line_length else ["--line-length", str(config.line_length)]

        if config.sort_imports:
            # ruff's isort rules (I) only. The backend emits imports in a fixed order but
            # cannot group them: which modules are first-party to the consuming project is
            # in that project's ruff config, which is why the destination path matters here.
            code = self._run(["ruff", "check", "--select", "I", "--fix-only", "--stdin-filename", stdin_filename, *line_length, "-"], code)

        cmd = ["ruff", "format", "--stdin-filename", stdin_filename, *line_length]
        if config.target_version:
            cmd.extend(["--target-version", config.target_version])
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
