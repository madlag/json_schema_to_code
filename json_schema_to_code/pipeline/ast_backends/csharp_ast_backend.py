"""
C# AST-based code generation backend.

Generates C# class code from IR using custom AST nodes.
"""

from __future__ import annotations

from typing import Any

from ..analyzer.ir_nodes import IR, ClassDef, FieldDef, TypeKind, TypeRef
from ..config import CodeGeneratorConfig
from .base import AstBackend
from .csharp_ast_nodes import (
    CSharpAttribute,
    CSharpClass,
    CSharpConstructor,
    CSharpEnum,
    CSharpEnumJsonConverter,
    CSharpEnumMember,
    CSharpField,
    CSharpFile,
    CSharpParameter,
    CSharpProperty,
    MemberModifier,
    UsingDirective,
)
from .csharp_serializer import CSharpSerializer


class CSharpAstBackend(AstBackend):
    """C# code generation backend using custom AST."""

    FILE_EXTENSION = "cs"

    TYPE_MAP = {
        "integer": "int",
        "string": "string",
        "boolean": "bool",
        "number": "float",
        "null": "null",
        "object": "object",
        "list": "List",
        "dict": "Dictionary",
        "tuple": "Tuple",
    }

    def __init__(self, config: CodeGeneratorConfig):
        super().__init__(config)
        self.required_imports: set[str] = set()
        self.enum_value_to_member: dict[str, dict[Any, str]] = {}
        self.serializer = CSharpSerializer()

    def generate(self, ir: IR) -> str:
        """Generate C# code from IR using AST."""
        # Reset import tracking
        self.required_imports = {"System", "Newtonsoft.Json"}

        # Build enum value to member mapping
        self.enum_value_to_member = {}
        for class_def in ir.classes:
            if class_def.is_enum and class_def.enum_def:
                value_to_member = {v: k for k, v in class_def.enum_def.members.items()}
                self.enum_value_to_member[class_def.name] = value_to_member

        # Build AST
        file = CSharpFile()

        # Generation comment
        file.generation_comment = ir.generation_comment

        # Generate classes and enums
        for class_def in ir.classes:
            if class_def.is_enum:
                enum_node, converter = self._generate_enum(class_def)
                if enum_node:
                    file.enums.append(enum_node)
                if converter:
                    file.enum_converters.append(converter)
            else:
                class_node = self._generate_class(class_def)
                if class_node:
                    file.classes.append(class_node)

        # Add using directives
        for ns in sorted(self.required_imports):
            file.using_directives.append(UsingDirective(namespace=ns))

        # Add additional using directives from config
        for ns in self.config.csharp_additional_usings:
            file.using_directives.append(UsingDirective(namespace=ns))

        # Set namespace from config
        if self.config.csharp_namespace:
            file.namespace = self.config.csharp_namespace

        # Serialize to source code
        return self.serializer.serialize(file)

    def _generate_class(self, class_def: ClassDef) -> CSharpClass:
        """Generate a class AST node from ClassDef."""
        cls = CSharpClass(name=class_def.name)

        # Attributes
        cls.attributes.append(CSharpAttribute(name="Serializable"))

        # Subtype handling
        if class_def.subclasses:
            self.required_imports.add("JsonSubTypes")
            disc_prop = class_def.discriminator_property or "type"
            cls.attributes.append(
                CSharpAttribute(
                    name="JsonConverter",
                    arguments=["typeof(JsonSubtypes)", f'"{disc_prop}"'],
                )
            )
            for subclass_name, discriminator in class_def.subclasses:
                cls.attributes.append(
                    CSharpAttribute(
                        name="JsonSubtypes.KnownSubType",
                        arguments=[f"typeof({subclass_name})", f'"{discriminator}"'],
                    )
                )

        # Base class
        if class_def.base_class:
            cls.base_class = class_def.base_class

        # Interfaces
        if class_def.implements:
            cls.interfaces.append(class_def.implements)

        # Fields and properties
        disc_prop_name = class_def.discriminator_property or "type"
        for field in class_def.fields:
            if field.is_const:
                # Emit discriminator const as get-only property so JSON serialization includes it
                if field.name == disc_prop_name:
                    prop_node = self._generate_discriminator_property(field)
                    if prop_node:
                        cls.properties.append(prop_node)
                else:
                    field_node = self._generate_field(field)
                    if field_node:
                        cls.fields.append(field_node)
            else:
                prop_node = self._generate_property(field)
                if prop_node:
                    cls.properties.append(prop_node)

        # Constructor
        constructor = self._generate_constructor(class_def)
        if constructor:
            cls.constructors.append(constructor)

        return cls

    def _generate_field(self, field: FieldDef) -> CSharpField | None:
        """Generate a field AST node (for const fields)."""
        if not field.type_ref:
            return None

        type_str = self.translate_type(field.type_ref)

        field_node = CSharpField(
            name=field.escaped_name or field.name,
            type_name=type_str,
            modifiers=[MemberModifier.CONST],
        )

        # JsonProperty attribute
        field_node.attributes.append(
            CSharpAttribute(
                name="JsonProperty",
                arguments=[f'"{field.name}"'],
            )
        )

        # Default value
        if field.has_default:
            field_node.default_value = self.format_default_value(field.default_value, field.type_ref)

        # Comment
        if field.comment:
            field_node.comment = field.comment

        return field_node

    def _generate_discriminator_property(self, field: FieldDef) -> CSharpProperty | None:
        """Generate a get-only property for discriminator (so it serializes to JSON)."""
        if not field.type_ref:
            return None
        type_str = self.translate_type(field.type_ref)
        pascal_name = self._get_property_name(field)
        prop = CSharpProperty(
            name=pascal_name,
            type_name=type_str,
            has_setter=False,
        )
        prop.attributes.append(CSharpAttribute(name="JsonProperty", arguments=[f'"{field.name}"']))
        if field.has_default:
            prop.default_value = self.format_default_value(field.default_value, field.type_ref)
        if field.comment:
            prop.comment = field.comment
        return prop

    def _generate_property(self, field: FieldDef) -> CSharpProperty | None:
        """Generate a property AST node."""
        if not field.type_ref:
            return None

        type_str = self.translate_type(field.type_ref)
        pascal_name = self._get_property_name(field)

        prop = CSharpProperty(
            name=pascal_name,
            type_name=type_str,
        )

        # JsonProperty attribute
        prop.attributes.append(
            CSharpAttribute(
                name="JsonProperty",
                arguments=[f'"{field.name}"'],
            )
        )

        # Default value
        if field.has_default:
            prop.default_value = self.format_default_value(field.default_value, field.type_ref)

        # Comment
        if field.comment:
            prop.comment = field.comment

        return prop

    def _get_property_name(self, field: FieldDef) -> str:
        """Get the property name (PascalCase)."""
        if field.is_interface_property and field.interface_property_name:
            return field.interface_property_name
        name = field.escaped_name or field.name
        return self._snake_to_pascal(name)

    def _generate_constructor(self, class_def: ClassDef) -> CSharpConstructor | None:
        """Generate a constructor AST node."""
        # Build parameters
        params: list[CSharpParameter] = []
        body: list[str] = []
        base_call_args: list[str] = []

        # Base class fields first
        for field in class_def.base_fields:
            if field.is_const:
                if field.is_overridden_const:
                    # Pass literal value to base
                    base_call_args.append(f'"{field.default_value}"')
                else:
                    # Pass variable name to base
                    base_call_args.append(field.name)
            else:
                # Regular property - add to params and base call
                type_str = self.translate_type(field.type_ref) if field.type_ref else "object"
                name = field.escaped_name or field.name
                params.append(CSharpParameter(name=name, type_name=type_str))
                base_call_args.append(name)

        # This class's constructor fields
        for field in class_def.constructor_fields:
            type_str = self.translate_type(field.type_ref) if field.type_ref else "object"
            name = field.escaped_name or field.name
            params.append(CSharpParameter(name=name, type_name=type_str))

            # Assignment in body
            pascal_name = self._get_property_name(field)
            body.append(f"this.{pascal_name} = {name};")

        # Add validation code to body
        if class_def.validation_code:
            body.append("")
            body.append("// Validate fields")
            body.extend(class_def.validation_code)

        return CSharpConstructor(
            class_name=class_def.name,
            parameters=params,
            base_call_args=base_call_args if class_def.base_class else [],
            body=body,
        )

    def _generate_enum(self, class_def: ClassDef) -> tuple[CSharpEnum | None, CSharpEnumJsonConverter | None]:
        """Generate an enum AST node and its JSON converter."""
        if not class_def.enum_def:
            return None, None

        self.required_imports.add("System.Collections.Generic")

        # Transform member names
        transformed_members = {}
        for name, value in class_def.enum_def.members.items():
            pascal_name = self._snake_to_pascal(name)
            transformed_members[pascal_name] = value

        # Enum node
        enum_node = CSharpEnum(name=class_def.name)
        for member_name in transformed_members:
            enum_node.members.append(CSharpEnumMember(name=member_name))

        # Converter node
        converter = CSharpEnumJsonConverter(
            enum_name=class_def.name,
            members=transformed_members,
        )

        return enum_node, converter

    def translate_type(self, type_ref: TypeRef) -> str:
        """Translate IR type to C# type string."""
        result = self._translate_type_inner(type_ref)

        # Handle nullability
        if type_ref.is_nullable and not result.endswith("?"):
            result = f"{result}?"

        return result

    def _translate_type_inner(self, type_ref: TypeRef) -> str:
        """Inner type translation without nullable handling."""
        if type_ref.kind == TypeKind.PRIMITIVE:
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)

        if type_ref.kind == TypeKind.CLASS:
            return type_ref.name

        if type_ref.kind == TypeKind.ANY:
            return "object"

        if type_ref.kind == TypeKind.ARRAY:
            self.required_imports.add("System.Collections.Generic")
            if type_ref.type_args:
                item_type = self.translate_type(type_ref.type_args[0])
                return f"List<{item_type}>"
            return "List<object>"

        if type_ref.kind == TypeKind.TUPLE:
            self.required_imports.add("System.Collections.Generic")
            if type_ref.type_args:
                item_types = ", ".join(self.translate_type(t) for t in type_ref.type_args)
                return f"Tuple<{item_types}>"
            return "Tuple<object>"

        if type_ref.kind == TypeKind.UNION:
            # C# doesn't support inline unions, use object
            types = [self.translate_type(t) for t in type_ref.type_args]
            non_null = [t for t in types if t != "null"]
            has_null = len(types) != len(non_null)

            if len(non_null) == 1:
                base_type = non_null[0]
                if has_null and not base_type.endswith("?"):
                    return f"{base_type}?"
                return base_type
            return "object"

        if type_ref.kind == TypeKind.CONST:
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)

        if type_ref.kind == TypeKind.ENUM:
            return self.TYPE_MAP.get(type_ref.name, "string")

        return "object"

    def format_default_value(self, value: Any, type_ref: TypeRef) -> str:
        """Format a default value for C#."""
        if value is None:
            return "null"

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, str):
            type_name = type_ref.name if type_ref else None
            if type_name and type_name in self.enum_value_to_member:
                value_to_member = self.enum_value_to_member[type_name]
                if value in value_to_member:
                    member_name = value_to_member[value]
                    return f"{type_name}.{member_name}"
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'

        if isinstance(value, (int, float)):
            # For C#, float literals need 'f' suffix
            if isinstance(value, float) or (type_ref and type_ref.name == "number"):
                return f"{value}f"
            return str(value)

        if isinstance(value, list):
            return self._format_list_default(value, type_ref)

        if isinstance(value, dict):
            return self._format_dict_default(value, type_ref)

        return str(value)

    def _format_list_default(self, value: list, type_ref: TypeRef) -> str:
        """Format a list default value for C#."""
        type_name = self.translate_type(type_ref)

        if len(value) == 0:
            return f"new {type_name}()"

        items = []
        for item in value:
            if isinstance(item, str):
                items.append(f'"{item}"')
            elif isinstance(item, bool):
                items.append("true" if item else "false")
            else:
                items.append(str(item))

        return f"new {type_name} {{{', '.join(items)}}}"

    def _format_dict_default(self, value: dict, type_ref: TypeRef) -> str:
        """Format a dict default value for C#."""
        type_name = self.translate_type(type_ref)

        if len(value) == 0:
            return f"new {type_name}()"

        items = []
        for k, v in value.items():
            key_str = f'"{k}"' if isinstance(k, str) else str(k)
            if isinstance(v, str):
                val_str = f'"{v}"'
            elif isinstance(v, bool):
                val_str = "true" if v else "false"
            else:
                val_str = str(v)
            items.append(f"[{key_str}] = {val_str}")

        return f"new {type_name} {{{', '.join(items)}}}"
