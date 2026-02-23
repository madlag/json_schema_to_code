"""
Atomic file writer for safe code generation.

Ensures that file writes are atomic to prevent data corruption
from interrupted operations.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from .base import CodeMergeError


class AtomicWriter:
    """Handles atomic file writes with validation.

    Uses a two-phase commit approach:
    1. Write to a temporary file in the same directory
    2. Validate the content
    3. Atomically replace the target file

    This ensures that an interrupted write operation never leaves
    the target file in an incomplete state.
    """

    def __init__(
        self,
        validate_python: Callable[[str], None] | None = None,
        validate_csharp: Callable[[str], None] | None = None,
        require_csharp_namespace: bool = False,
    ):
        """Initialize the atomic writer.

        Args:
            validate_python: Optional validation function for Python code
            validate_csharp: Optional validation function for C# code
            require_csharp_namespace: Whether to require a namespace declaration in C# output
        """
        self._validate_python = validate_python or self._default_validate_python
        self._validate_csharp = validate_csharp or self._default_validate_csharp
        self._require_csharp_namespace = require_csharp_namespace

    def write(
        self,
        path: Path,
        content: str,
        language: str,
        validate: bool = True,
    ) -> None:
        """Write content to file atomically.

        Args:
            path: Target file path
            content: Content to write
            language: Language for validation ("python" or "cs")
            validate: Whether to validate before finalizing

        Raises:
            CodeMergeError: If validation fails
            OSError: If file operations fail
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary file in the same directory
        # Same directory ensures atomic rename on the same filesystem
        temp_fd, temp_path_str = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )

        temp_path = Path(temp_path_str)

        try:
            # Write content to temporary file
            with open(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)

            # Validate if requested
            if validate:
                self._validate_content(content, language)

            # Atomic replace
            # On POSIX systems, rename() is atomic if source and dest are on same filesystem
            temp_path.replace(path)

        except Exception:
            # Clean up temp file on any error
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise

    def write_if_not_exists(
        self,
        path: Path,
        content: str,
        language: str,
        validate: bool = True,
    ) -> bool:
        """Write content only if the file doesn't exist.

        Args:
            path: Target file path
            content: Content to write
            language: Language for validation ("python" or "cs")
            validate: Whether to validate before finalizing

        Returns:
            True if file was written, False if it already exists

        Raises:
            FileExistsError: If the file already exists
            CodeMergeError: If validation fails
        """
        if path.exists():
            raise FileExistsError(f"Output file already exists: {path}. Use force mode to overwrite or merge mode to preserve custom code.")

        self.write(path, content, language, validate)
        return True

    def _validate_content(self, content: str, language: str) -> None:
        """Validate content based on language.

        Args:
            content: The content to validate
            language: The language ("python" or "cs")

        Raises:
            CodeMergeError: If validation fails
        """
        if language == "python":
            self._validate_python(content)
        elif language == "cs":
            self._validate_csharp(content)
        else:
            # Unknown language, skip validation
            pass

    def _default_validate_python(self, content: str) -> None:
        """Default Python validation.

        Args:
            content: Python code to validate

        Raises:
            CodeMergeError: If validation fails
        """
        import ast

        try:
            ast.parse(content)
        except SyntaxError as e:
            raise CodeMergeError(f"Generated Python code is not valid: {e}") from e

        # Check for minimum expected content
        if "from __future__ import annotations" not in content:
            # Not strictly required, but expected in our output
            pass

        if "@dataclass" not in content and "class " in content:
            # Check we have some class structure
            pass

    def _default_validate_csharp(self, content: str) -> None:
        """Default C# validation.

        Args:
            content: C# code to validate

        Raises:
            CodeMergeError: If validation fails
        """
        # Basic structural checks (no full parsing without tree-sitter)
        if self._require_csharp_namespace and "namespace " not in content:
            raise CodeMergeError("Generated C# code is missing namespace declaration")

        if "class " not in content and "enum " not in content:
            raise CodeMergeError("Generated C# code has no type definitions")

        # Check for balanced braces (simple heuristic)
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces != close_braces:
            raise CodeMergeError(f"Generated C# code has unbalanced braces: {open_braces} open, {close_braces} close")

        # Check for using statements
        if "using " not in content:
            raise CodeMergeError("Generated C# code is missing using statements")
