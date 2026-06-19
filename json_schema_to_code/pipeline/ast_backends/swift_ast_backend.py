"""
Swift AST-based code generation backend.

Generates Swift ``Codable`` structs/enums from the IR. Type model (see plan):
- JSON objects -> ``struct``s conforming to ``Codable``.
- ``allOf`` inheritance -> base fields flattened into each struct.
- Discriminated polymorphic bases -> a generated ``enum`` (``SwiftPolyEnum``) that
  switches on the discriminator in ``init(from:)``.
- String enums -> raw-value ``Codable`` enums (Swift maps raw value <-> JSON for free).

The generated code references an ``AnyCodable`` helper type (for schema ``object`` /
untyped ``Any``); the consuming Swift module must provide it once.
"""

from __future__ import annotations

from typing import Any

from ..analyzer.ir_nodes import IR, ClassDef, FieldDef, TypeKind, TypeRef
from ..config import CodeGeneratorConfig
from .base import AstBackend
from .swift_ast_nodes import (
    SwiftEnum,
    SwiftEnumCase,
    SwiftFile,
    SwiftPolyEnum,
    SwiftPolyEnumCase,
    SwiftProperty,
    SwiftStruct,
)
from .swift_serializer import SwiftSerializer

# Swift reserved words that must be backtick-escaped when used as identifiers.
SWIFT_RESERVED_KEYWORDS = {
    "associatedtype",
    "class",
    "deinit",
    "enum",
    "extension",
    "fileprivate",
    "func",
    "import",
    "init",
    "inout",
    "internal",
    "let",
    "open",
    "operator",
    "private",
    "precedencegroup",
    "protocol",
    "public",
    "rethrows",
    "static",
    "struct",
    "subscript",
    "typealias",
    "var",
    "break",
    "case",
    "catch",
    "continue",
    "default",
    "defer",
    "do",
    "else",
    "fallthrough",
    "for",
    "guard",
    "if",
    "in",
    "repeat",
    "return",
    "throw",
    "switch",
    "where",
    "while",
    "as",
    "any",
    "await",
    "false",
    "is",
    "nil",
    "self",
    "Self",
    "super",
    "throws",
    "true",
    "try",
    "Type",
    "Protocol",
}


class SwiftAstBackend(AstBackend):
    """Swift code generation backend using a small Swift AST."""

    FILE_EXTENSION = "swift"

    TYPE_MAP = {
        "integer": "Int",
        "string": "String",
        "boolean": "Bool",
        "number": "Double",
        "null": "Void",
        "object": "AnyCodable",
    }

    def __init__(self, config: CodeGeneratorConfig):
        super().__init__(config)
        self.serializer = SwiftSerializer()
        self.enum_names: set[str] = set()
        # enum type name -> {json_value: swift_case_name}
        self.enum_value_to_member: dict[str, dict[Any, str]] = {}
        # class name -> {json_key: FieldDef} (for struct-typed default initializers)
        self.class_field_map: dict[str, dict[str, FieldDef]] = {}

    # ------------------------------------------------------------------ generate

    def generate(self, ir: IR) -> str:
        """Generate Swift code from the IR."""
        self.enum_names = {c.name for c in ir.classes if c.is_enum}
        self.enum_value_to_member = {}
        self.class_field_map = {}
        for class_def in ir.classes:
            if class_def.is_enum and class_def.enum_def:
                self.enum_value_to_member[class_def.name] = {json_value: self._swift_ident(self._lower_camel(member)) for member, json_value in class_def.enum_def.members.items()}
            elif not (class_def.is_polymorphic_base and class_def.subclasses):
                self.class_field_map[class_def.name] = {f.original_name or f.name: f for f in (class_def.base_fields + class_def.fields)}

        file = SwiftFile()
        file.generation_comment = ir.generation_comment

        for class_def in ir.classes:
            if class_def.is_enum:
                node = self._generate_enum(class_def)
                if node:
                    file.enums.append(node)
            elif class_def.is_polymorphic_base and class_def.subclasses:
                file.poly_enums.append(self._generate_poly_enum(class_def))
            else:
                file.structs.append(self._generate_struct(class_def))

        return self.serializer.serialize(file)

    # -------------------------------------------------------------------- nodes

    def _generate_enum(self, class_def: ClassDef) -> SwiftEnum | None:
        enum_def = class_def.enum_def
        if not enum_def:
            return None
        raw_type = "Int" if enum_def.value_type == "integer" else "String"
        node = SwiftEnum(name=class_def.name, raw_type=raw_type)
        for member, json_value in enum_def.members.items():
            node.cases.append(
                SwiftEnumCase(
                    name=self._swift_ident(self._lower_camel(member)),
                    raw_value=str(json_value),
                )
            )
        return node

    def _generate_poly_enum(self, class_def: ClassDef) -> SwiftPolyEnum:
        disc_key = class_def.discriminator_property or "type"
        node = SwiftPolyEnum(name=class_def.name, discriminator_key=disc_key)
        for subtype_name, disc_value in class_def.subclasses:
            node.cases.append(
                SwiftPolyEnumCase(
                    name=self._swift_ident(self._lower_camel(subtype_name)),
                    concrete_type=subtype_name,
                    discriminator_value=str(disc_value),
                )
            )
        return node

    def _generate_struct(self, class_def: ClassDef) -> SwiftStruct:
        node = SwiftStruct(name=class_def.name)

        # Flatten base fields + own fields; own fields override base fields by JSON key.
        ordered: list[FieldDef] = []
        index_by_key: dict[str, int] = {}
        for field in class_def.base_fields + class_def.fields:
            if field.name in self.config.global_ignore_fields:
                continue
            key = field.name
            if key in index_by_key:
                ordered[index_by_key[key]] = field
            else:
                index_by_key[key] = len(ordered)
                ordered.append(field)

        needs_decoder = False
        for field in ordered:
            prop = self._generate_property(field)
            if prop is None:
                continue
            node.properties.append(prop)
            if prop.default_value is not None:
                needs_decoder = True

        node.needs_custom_decoder = needs_decoder
        return node

    def _generate_property(self, field: FieldDef) -> SwiftProperty | None:
        if not field.type_ref:
            return None
        swift_type = self.translate_type(field.type_ref)
        default = None
        if field.has_default:
            default = self.format_default_value(field.default_value, field.type_ref)
        return SwiftProperty(
            name=self._swift_ident(self._lower_camel(field.name)),
            type_name=swift_type,
            json_key=field.original_name or field.name,
            is_optional=field.type_ref.is_nullable,
            default_value=default,
            comment=field.comment,
        )

    # ---------------------------------------------------------------- type xlate

    def translate_type(self, type_ref: TypeRef) -> str:
        result = self._translate_type_inner(type_ref)
        if type_ref.is_nullable and not result.endswith("?"):
            result = f"{result}?"
        return result

    def _translate_type_inner(self, type_ref: TypeRef) -> str:
        kind = type_ref.kind
        if kind == TypeKind.PRIMITIVE:
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)
        if kind == TypeKind.CLASS:
            return type_ref.name
        if kind == TypeKind.ANY:
            return "AnyCodable"
        if kind == TypeKind.DICT:
            if len(type_ref.type_args) == 2:
                key = self.translate_type(type_ref.type_args[0])
                value = self.translate_type(type_ref.type_args[1])
                return f"[{key}: {value}]"
            return "[String: AnyCodable]"
        if kind == TypeKind.ARRAY:
            if type_ref.type_args:
                return f"[{self.translate_type(type_ref.type_args[0])}]"
            return "[AnyCodable]"
        if kind == TypeKind.TUPLE:
            # Swift tuples are not Codable; represent as a heterogeneous array.
            return "[AnyCodable]"
        if kind == TypeKind.UNION:
            types = [self.translate_type(t) for t in type_ref.type_args]
            non_null = [t for t in types if t not in ("Void", "null")]
            has_null = len(types) != len(non_null)
            if len(non_null) == 1:
                base = non_null[0]
                if has_null and not base.endswith("?"):
                    return f"{base}?"
                return base
            # Heterogeneous union with no generated poly-enum -> AnyCodable.
            return "AnyCodable"
        if kind == TypeKind.CONST:
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)
        if kind == TypeKind.ENUM:
            # Inline enum (no generated type) -> raw String, like the C# backend.
            return "String"
        return "AnyCodable"

    # ------------------------------------------------------------- default values

    def format_default_value(self, value: Any, type_ref: TypeRef | None) -> str:
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            type_name = type_ref.name if type_ref else None
            if type_name and type_name in self.enum_value_to_member:
                member = self.enum_value_to_member[type_name].get(value)
                if member:
                    return f".{member}"
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return self._format_list_default(value, type_ref)
        if isinstance(value, dict):
            return self._format_dict_default(value, type_ref)
        return str(value)

    def _format_list_default(self, value: list, type_ref: TypeRef | None) -> str:
        if not value:
            return "[]"
        element_type = type_ref.type_args[0] if type_ref and type_ref.type_args else None
        items = [self.format_default_value(item, element_type) for item in value]
        return "[" + ", ".join(items) + "]"

    def _format_dict_default(self, value: dict, type_ref: TypeRef | None) -> str:
        if type_ref and type_ref.kind == TypeKind.CLASS:
            return self._format_struct_initializer(value, type_ref)
        if not value:
            return "[:]"
        value_type = type_ref.type_args[1] if type_ref and len(type_ref.type_args) == 2 else None
        items = []
        for k, v in value.items():
            key_str = f'"{k}"' if isinstance(k, str) else str(k)
            items.append(f"{key_str}: {self.format_default_value(v, value_type)}")
        return "[" + ", ".join(items) + "]"

    def _format_struct_initializer(self, value: dict, type_ref: TypeRef) -> str:
        base_name = self.translate_type(type_ref).rstrip("?")
        field_map = self.class_field_map.get(type_ref.name, {})
        items = []
        for k, v in value.items():
            field_def = field_map.get(k)
            label = self._swift_ident(self._lower_camel(k))
            field_type = field_def.type_ref if field_def else None
            items.append(f"{label}: {self.format_default_value(v, field_type)}")
        return f"{base_name}(" + ", ".join(items) + ")"

    # -------------------------------------------------------------------- helpers

    def _lower_camel(self, text: str) -> str:
        pascal = self._snake_to_pascal(text)
        return pascal[0].lower() + pascal[1:] if pascal else pascal

    def _swift_ident(self, name: str) -> str:
        return f"`{name}`" if name in SWIFT_RESERVED_KEYWORDS else name
