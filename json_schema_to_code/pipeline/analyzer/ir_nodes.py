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

    # Explicit per-language types from `x-<language>-type` keys on the schema node
    # (language -> verbatim type, e.g. {"python": "datetime", "swift": "[NamedWidget]"}).
    # The schema names the type to emit instead of the inferred one, for shapes the
    # generator must not own: a hand-written class, a foreign payload, a scalar $def.
    type_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class FieldDef:
    """A field definition in a class."""

    name: str = ""
    original_name: str = ""  # Original JSON property name
    type_ref: TypeRef | None = None
    is_required: bool = False
    default_value: Any = None
    has_default: bool = False

    # x-omit-when-default: leave the field out of the serialized form when it
    # still holds its default (Python backend).
    omit_when_default: bool = False

    # For C# keyword escaping
    escaped_name: str | None = None

    # For C# const modifier
    is_const: bool = False

    # For allOf inheritance: whether this const was overridden (use literal)
    # or inherited (use variable name)
    is_overridden_const: bool = False

    # Set on a base_field when the immediate parent class already constified
    # the field at its own level (typical multi-level allOf chain). The
    # parent's constructor absorbs the const internally and does NOT take it
    # as a parameter, so a derived class's ``base(...)`` call must skip this
    # field — even if the derived class re-overrides the const value (which
    # is then expressed via the C# ``override`` getter on the derived class
    # itself, not via the constructor).
    is_skipped_in_base_call: bool = False

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
    base_class: str | None = None  # Name of primary base class
    extra_base_classes: list[str] = field(default_factory=list)  # Additional base classes (multiple inheritance)
    subclasses: list[tuple[str, str]] = field(default_factory=list)  # [(name, discriminator), ...]
    # JSON property used for discriminator (e.g. "type", "action_type"). None => "type" in C# backend.
    discriminator_property: str | None = None
    # True when this is a genuine discriminated-union / known-subtypes base (oneOf/anyOf or an
    # explicit "discriminator" / x-*-known-subtypes), as opposed to a plain allOf inheritance base.
    # The Swift backend emits a discriminated enum only for these; plain inheritance bases stay structs.
    is_polymorphic_base: bool = False
    # C# using directives required by cross-schema known subtypes
    subtype_usings: list[str] = field(default_factory=list)

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
