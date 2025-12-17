"""
IR (Intermediate Representation) node definitions.

These nodes represent the analyzed and resolved schema, ready for
code generation. All references are resolved and types are determined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TypeKind(Enum):
    """Kind of type in the IR."""

    PRIMITIVE = "primitive"  # int, str, bool, float, None
    CLASS = "class"  # A generated class
    ARRAY = "array"  # list[T]
    TUPLE = "tuple"  # tuple[T, U, ...]
    DICT = "dict"  # dict[K, V]
    UNION = "union"  # T | U | ...
    OPTIONAL = "optional"  # T | None
    ENUM = "enum"  # Enum type
    CONST = "const"  # Literal type
    ANY = "any"  # Any type
    TYPE_ALIAS = "type_alias"  # Reference to a type alias


@dataclass
class TypeRef:
    """A resolved type reference."""

    kind: TypeKind = TypeKind.PRIMITIVE
    name: str = ""  # Type name (e.g., "int", "MyClass")

    # For container types
    type_args: list[TypeRef] = field(default_factory=list)

    # For const/literal types
    const_value: Any = None

    # For enums
    enum_values: list[Any] = field(default_factory=list)
    enum_member_names: dict[Any, str] = field(default_factory=dict)

    # Whether this type should be quoted (forward reference)
    is_quoted: bool = False

    # For optional types with default
    default_value: Any = None
    has_default: bool = False

    # Whether this is a nullable type
    is_nullable: bool = False


@dataclass
class FieldDef:
    """A field definition in a class."""

    name: str = ""
    original_name: str = ""  # Original JSON property name
    type_ref: TypeRef | None = None
    is_required: bool = False
    default_value: Any = None
    has_default: bool = False

    # For C# keyword escaping
    escaped_name: str | None = None

    # For C# const modifier
    is_const: bool = False

    # For allOf inheritance: whether this const was overridden (use literal)
    # or inherited (use variable name)
    is_overridden_const: bool = False

    # For C# interface implementation
    is_interface_property: bool = False
    interface_property_name: str | None = None

    # Comment to add after field
    comment: str | None = None


@dataclass
class EnumDef:
    """An enum definition."""

    name: str = ""
    original_name: str = ""
    value_type: str = "string"  # "string", "integer", etc.
    members: dict[str, Any] = field(default_factory=dict)  # member_name -> json_value


@dataclass
class TypeAlias:
    """A type alias definition."""

    name: str = ""
    target_type: TypeRef | None = None
    # For rendering: the union components
    union_components: list[str] = field(default_factory=list)
    # Whether this alias references classes defined in this schema
    has_forward_refs: bool = False


@dataclass
class ClassDef:
    """A class definition."""

    name: str = ""
    original_name: str = ""  # Original definition key

    # Inheritance
    base_class: str | None = None  # Name of base class
    subclasses: list[tuple[str, str]] = field(default_factory=list)  # [(name, discriminator), ...]

    # Fields
    fields: list[FieldDef] = field(default_factory=list)

    # For inherited fields (base class fields)
    base_fields: list[FieldDef] = field(default_factory=list)

    # Constructor fields (excludes const fields)
    constructor_fields: list[FieldDef] = field(default_factory=list)

    # For C# interface implementation
    implements: str | None = None
    interface_properties: dict[str, str] = field(default_factory=dict)

    # For enum classes
    is_enum: bool = False
    enum_def: EnumDef | None = None

    # Validation code lines
    validation_code: list[str] = field(default_factory=list)


@dataclass
class ImportDef:
    """An import definition."""

    module: str = ""  # Module to import from
    names: list[str] = field(default_factory=list)  # Names to import


@dataclass
class IR:
    """The complete Intermediate Representation."""

    root_name: str = ""

    # All class definitions (in generation order)
    classes: list[ClassDef] = field(default_factory=list)

    # Type aliases (unions)
    type_aliases: list[TypeAlias] = field(default_factory=list)

    # Required imports
    imports: list[ImportDef] = field(default_factory=list)

    # Enum definitions (for C# separate enum generation)
    enums: list[EnumDef] = field(default_factory=list)

    # Generation comment
    generation_comment: str = ""

    # Mapping from definition name to class name
    name_mapping: dict[str, str] = field(default_factory=dict)
