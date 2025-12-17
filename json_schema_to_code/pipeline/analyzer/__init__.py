"""
Analyzer module.

Contains reference resolution, name resolution, and IR building.
"""

from __future__ import annotations

from .analyzer import SchemaAnalyzer
from .ir_nodes import (
    IR,
    ClassDef,
    EnumDef,
    FieldDef,
    TypeAlias,
    TypeRef,
)

__all__ = [
    "ClassDef",
    "FieldDef",
    "TypeRef",
    "EnumDef",
    "TypeAlias",
    "IR",
    "SchemaAnalyzer",
]
