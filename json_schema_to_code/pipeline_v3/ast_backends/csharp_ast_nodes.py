"""
C# AST node definitions.

These nodes represent the structure of C# source files for code generation.
They are used to build a C# AST which is then serialized to source code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessModifier(str, Enum):
    """C# access modifiers."""

    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"


class MemberModifier(str, Enum):
    """C# member modifiers."""

    STATIC = "static"
    CONST = "const"
    READONLY = "readonly"
    ABSTRACT = "abstract"
    VIRTUAL = "virtual"
    OVERRIDE = "override"
    SEALED = "sealed"


@dataclass
class CSharpNode:
    """Base class for all C# AST nodes."""

    pass


@dataclass
class CSharpAttribute(CSharpNode):
    """Represents a C# attribute (e.g., [JsonProperty("name")])."""

    name: str = ""
    arguments: list[str] = field(default_factory=list)

    def to_string(self) -> str:
        """Convert to attribute string."""
        if self.arguments:
            args_str = ", ".join(self.arguments)
            return f"[{self.name}({args_str})]"
        return f"[{self.name}]"


@dataclass
class CSharpParameter(CSharpNode):
    """Represents a method/constructor parameter."""

    name: str = ""
    type_name: str = ""
    default_value: str | None = None


@dataclass
class CSharpField(CSharpNode):
    """Represents a class field."""

    name: str = ""
    type_name: str = ""
    access: AccessModifier = AccessModifier.PUBLIC
    modifiers: list[MemberModifier] = field(default_factory=list)
    default_value: str | None = None
    attributes: list[CSharpAttribute] = field(default_factory=list)
    comment: str | None = None


@dataclass
class CSharpProperty(CSharpNode):
    """Represents a class property with get/set."""

    name: str = ""
    type_name: str = ""
    access: AccessModifier = AccessModifier.PUBLIC
    has_getter: bool = True
    has_setter: bool = True
    default_value: str | None = None
    attributes: list[CSharpAttribute] = field(default_factory=list)
    comment: str | None = None


@dataclass
class CSharpConstructor(CSharpNode):
    """Represents a class constructor."""

    class_name: str = ""
    access: AccessModifier = AccessModifier.PUBLIC
    parameters: list[CSharpParameter] = field(default_factory=list)
    base_call_args: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)  # Assignment statements


@dataclass
class CSharpMethod(CSharpNode):
    """Represents a class method."""

    name: str = ""
    return_type: str = "void"
    access: AccessModifier = AccessModifier.PUBLIC
    modifiers: list[MemberModifier] = field(default_factory=list)
    parameters: list[CSharpParameter] = field(default_factory=list)
    body: list[str] = field(default_factory=list)


@dataclass
class CSharpEnumMember(CSharpNode):
    """Represents an enum member."""

    name: str = ""
    value: str | None = None


@dataclass
class CSharpEnum(CSharpNode):
    """Represents an enum declaration."""

    name: str = ""
    access: AccessModifier = AccessModifier.PUBLIC
    members: list[CSharpEnumMember] = field(default_factory=list)
    attributes: list[CSharpAttribute] = field(default_factory=list)


@dataclass
class CSharpClass(CSharpNode):
    """Represents a class declaration."""

    name: str = ""
    access: AccessModifier = AccessModifier.PUBLIC
    base_class: str | None = None
    interfaces: list[str] = field(default_factory=list)
    attributes: list[CSharpAttribute] = field(default_factory=list)
    fields: list[CSharpField] = field(default_factory=list)
    properties: list[CSharpProperty] = field(default_factory=list)
    constructors: list[CSharpConstructor] = field(default_factory=list)
    methods: list[CSharpMethod] = field(default_factory=list)
    nested_classes: list[CSharpClass] = field(default_factory=list)
    nested_enums: list[CSharpEnum] = field(default_factory=list)


@dataclass
class CSharpEnumJsonConverter(CSharpNode):
    """Represents a JSON converter class for an enum."""

    enum_name: str = ""
    members: dict[str, str] = field(default_factory=dict)  # member_name -> json_value


@dataclass
class UsingDirective(CSharpNode):
    """Represents a using directive."""

    namespace: str = ""


@dataclass
class CSharpFile(CSharpNode):
    """Represents a complete C# source file."""

    using_directives: list[UsingDirective] = field(default_factory=list)
    generation_comment: str = ""
    namespace: str | None = None  # Optional namespace to wrap all types
    classes: list[CSharpClass] = field(default_factory=list)
    enums: list[CSharpEnum] = field(default_factory=list)
    enum_converters: list[CSharpEnumJsonConverter] = field(default_factory=list)
