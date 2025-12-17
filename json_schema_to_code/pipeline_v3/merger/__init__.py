"""
Merger module for V3 pipeline.

Provides AST-level merging of generated code with existing files,
preserving custom code like imports, constants, and methods.
"""

from __future__ import annotations

from .atomic_writer import AtomicWriter
from .base import AstMerger, CodeMergeError
from .csharp_merger import CSharpAstMerger
from .python_merger import PythonAstMerger

__all__ = [
    "AstMerger",
    "CodeMergeError",
    "PythonAstMerger",
    "CSharpAstMerger",
    "AtomicWriter",
]
