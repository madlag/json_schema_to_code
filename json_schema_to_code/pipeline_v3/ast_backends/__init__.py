"""
AST-based code generation backends.

These backends generate code using language-native AST representations
instead of template-based string generation.
"""

from __future__ import annotations

from .base import AstBackend
from .csharp_ast_backend import CSharpAstBackend
from .python_ast_backend import PythonAstBackend

__all__ = [
    "AstBackend",
    "PythonAstBackend",
    "CSharpAstBackend",
]
