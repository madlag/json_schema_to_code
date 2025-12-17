"""
AST (Abstract Syntax Tree) node definitions for JSON Schema.

These nodes represent the parsed structure of a JSON Schema before
any reference resolution or language-specific processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaNode:
    """Base class for all AST nodes."""

    # Original source location in schema (for error messages)
    source_path: str = ""

    # Raw schema metadata (x-* extensions, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PrimitiveNode(SchemaNode):
    """Represents a primitive type (string, integer, number, boolean, null)."""

    type_name: str = ""  # "string", "integer", "number", "boolean", "null", "object"

    # Validation constraints
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    exclusive_maximum: float | None = None
    multiple_of: float | None = None


@dataclass
class ConstNode(SchemaNode):
    """Represents a const value."""

    value: Any = None
    inferred_type: str = ""  # "string", "integer", etc.


@dataclass
class EnumNode(SchemaNode):
    """Represents an enum type."""

    values: list[Any] = field(default_factory=list)
    inferred_type: str = ""  # "string", "integer", etc.

    # Custom member names from x-enum-members
    member_names: dict[Any, str] = field(default_factory=dict)


@dataclass
class RefNode(SchemaNode):
    """Represents a $ref (unresolved reference)."""

    ref_path: str = ""  # e.g., "#/definitions/MyClass" or external path

    # Optional class name override from x-ref-class-name
    class_name_override: str | None = None


@dataclass
class ArrayNode(SchemaNode):
    """Represents an array type."""

    items: SchemaNode | list[SchemaNode] | None = None  # Single type or tuple types
    min_items: int | None = None
    max_items: int | None = None


@dataclass
class PropertyDef(SchemaNode):
    """Represents a property in an object."""

    name: str = ""
    type_node: SchemaNode | None = None
    is_required: bool = False
    default_value: Any = None
    has_default: bool = False


@dataclass
class ObjectNode(SchemaNode):
    """Represents an object type with properties."""

    properties: list[PropertyDef] = field(default_factory=list)
    required: list[str] = field(default_factory=list)

    # C# interface implementation
    implements: str | None = None
    interface_properties: dict[str, str] = field(default_factory=dict)


@dataclass
class UnionNode(SchemaNode):
    """Represents a oneOf or anyOf union type."""

    variants: list[SchemaNode] = field(default_factory=list)
    union_type: str = "oneOf"  # "oneOf" or "anyOf"


@dataclass
class AllOfNode(SchemaNode):
    """Represents inheritance via allOf."""

    base_ref: RefNode | None = None  # The $ref part
    extension: ObjectNode | None = None  # The extension properties


@dataclass
class DefinitionNode(SchemaNode):
    """Represents a definition ($defs or definitions entry)."""

    name: str = ""
    original_name: str = ""  # Original key in schema (before PascalCase conversion)
    body: SchemaNode | None = None


@dataclass
class SchemaAST:
    """Root of the parsed schema AST."""

    root_name: str = ""
    root_node: SchemaNode | None = None  # Top-level schema if it has properties
    definitions: list[DefinitionNode] = field(default_factory=list)

    # Raw schema for reference
    raw_schema: dict[str, Any] = field(default_factory=dict)
