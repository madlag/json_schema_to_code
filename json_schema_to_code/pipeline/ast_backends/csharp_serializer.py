"""
C# AST Serializer.

Converts C# AST nodes to properly-formatted C# source code.
Follows C# style guidelines:
- Braces on new lines (Allman style)
- 4-space indentation
- Blank line between members
- Properties use PascalCase
- Attributes on separate lines above declarations
"""

from __future__ import annotations

from .csharp_ast_nodes import (
    CSharpClass,
    CSharpConstructor,
    CSharpEnum,
    CSharpEnumJsonConverter,
    CSharpField,
    CSharpFile,
    CSharpMethod,
    CSharpProperty,
    UsingDirective,
)


class CSharpSerializer:
    """Serializes C# AST nodes to source code."""

    INDENT = "    "  # 4 spaces

    def serialize(self, file: CSharpFile) -> str:
        """Serialize a complete C# file to source code."""
        lines: list[str] = []

        # Generation comment
        if file.generation_comment:
            lines.append(file.generation_comment)

        # Using directives
        for using in file.using_directives:
            lines.append(self._serialize_using(using))

        if file.using_directives:
            lines.append("")

        # Namespace wrapping
        if file.namespace:
            lines.append(f"namespace {file.namespace}")
            lines.append("{")
            indent_level = 1
        else:
            indent_level = 0

        # Enums and their converters
        for enum in file.enums:
            enum_lines = self._serialize_enum_with_converter(enum, file.enum_converters)
            lines.extend(self._indent_lines(enum_lines, indent_level))

        # Classes
        for cls in file.classes:
            class_lines = self._serialize_class(cls)
            lines.extend(self._indent_lines(class_lines, indent_level))

        # Close namespace
        if file.namespace:
            lines.append("}")

        return "\n".join(lines)

    def _indent_lines(self, lines: list[str], level: int) -> list[str]:
        """Add indentation to a list of lines."""
        if level == 0:
            return lines
        prefix = self.INDENT * level
        return [prefix + line if line.strip() else line for line in lines]

    def _serialize_using(self, using: UsingDirective) -> str:
        """Serialize a using directive."""
        return f"using {using.namespace};"

    def _serialize_enum_with_converter(
        self,
        enum: CSharpEnum,
        converters: list[CSharpEnumJsonConverter],
    ) -> list[str]:
        """Serialize an enum with its JSON converter."""
        lines: list[str] = []

        # Find matching converter
        converter = next((c for c in converters if c.enum_name == enum.name), None)

        # Enum attributes
        if converter:
            lines.append(f"[JsonConverter(typeof({enum.name}JsonConverter))]")

        for attr in enum.attributes:
            lines.append(attr.to_string())

        # Enum declaration
        lines.append(f"public enum {enum.name}")
        lines.append("{")

        # Enum members
        for i, member in enumerate(enum.members):
            comma = "," if i < len(enum.members) - 1 else ""
            lines.append(f"{self.INDENT}{member.name}{comma}")
            lines.append("")

        lines.append("}")
        lines.append("")

        # JSON converter class
        if converter:
            lines.extend(self._serialize_enum_converter(converter))

        return lines

    def _serialize_enum_converter(self, converter: CSharpEnumJsonConverter) -> list[str]:
        """Serialize an enum JSON converter class."""
        lines: list[str] = []
        enum_name = converter.enum_name

        lines.append(f"public class {enum_name}JsonConverter : JsonConverter<{enum_name}>")
        lines.append("{")

        # StringToEnum dictionary
        lines.append(f"{self.INDENT}private static readonly Dictionary<string, {enum_name}> StringToEnum = new Dictionary<string, {enum_name}>")
        lines.append(f"{self.INDENT}{{")
        members_list = list(converter.members.items())
        for i, (member_name, json_value) in enumerate(members_list):
            comma = "," if i < len(members_list) - 1 else ""
            lines.append(f'{self.INDENT}{self.INDENT}{{ "{json_value}", {enum_name}.{member_name} }}{comma}')
        lines.append(f"{self.INDENT}}};")
        lines.append("")

        # EnumToString dictionary
        lines.append(f"{self.INDENT}private static readonly Dictionary<{enum_name}, string> EnumToString = new Dictionary<{enum_name}, string>")
        lines.append(f"{self.INDENT}{{")
        for i, (member_name, json_value) in enumerate(members_list):
            comma = "," if i < len(members_list) - 1 else ""
            lines.append(f'{self.INDENT}{self.INDENT}{{ {enum_name}.{member_name}, "{json_value}" }}{comma}')
        lines.append(f"{self.INDENT}}};")
        lines.append("")

        # WriteJson method
        lines.append(f"{self.INDENT}public override void WriteJson(JsonWriter writer, {enum_name} value, JsonSerializer serializer)")
        lines.append(f"{self.INDENT}{{")
        lines.append(f"{self.INDENT}{self.INDENT}writer.WriteValue(EnumToString[value]);")
        lines.append(f"{self.INDENT}}}")
        lines.append("")

        # ReadJson method
        lines.append(f"{self.INDENT}public override {enum_name} ReadJson(JsonReader reader, Type objectType, {enum_name} existingValue, bool hasExistingValue, JsonSerializer serializer)")
        lines.append(f"{self.INDENT}{{")
        lines.append(f"{self.INDENT}{self.INDENT}string stringValue = (string)reader.Value;")
        lines.append(f"{self.INDENT}{self.INDENT}return StringToEnum[stringValue];")
        lines.append(f"{self.INDENT}}}")

        lines.append("}")
        lines.append("")

        return lines

    def _serialize_class(self, cls: CSharpClass, indent: int = 0) -> list[str]:
        """Serialize a class declaration."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Attributes
        for attr in cls.attributes:
            lines.append(f"{prefix}{attr.to_string()}")

        # Class declaration
        declaration = f"{prefix}{cls.access.value} class {cls.name}"
        if cls.base_class:
            declaration += f" : {cls.base_class}"
        elif cls.interfaces:
            declaration += f" : {', '.join(cls.interfaces)}"

        lines.append(declaration)
        lines.append(f"{prefix}{{")

        prefix + self.INDENT

        # Fields (const fields)
        for field in cls.fields:
            lines.extend(self._serialize_field(field, indent + 1))

        # Properties
        for prop in cls.properties:
            lines.extend(self._serialize_property(prop, indent + 1))

        # Constructors
        for constructor in cls.constructors:
            lines.extend(self._serialize_constructor(constructor, indent + 1))

        # Methods
        for method in cls.methods:
            lines.extend(self._serialize_method(method, indent + 1))

        # Nested enums
        for nested_enum in cls.nested_enums:
            lines.extend(self._serialize_enum_simple(nested_enum, indent + 1))

        # Nested classes
        for nested_cls in cls.nested_classes:
            lines.extend(self._serialize_class(nested_cls, indent + 1))

        lines.append(f"{prefix}}}")
        lines.append("")

        return lines

    def _serialize_field(self, field: CSharpField, indent: int) -> list[str]:
        """Serialize a field declaration."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Attributes
        for attr in field.attributes:
            lines.append(f"{prefix}{attr.to_string()}")

        # Field declaration
        modifiers = " ".join(m.value for m in field.modifiers)
        if modifiers:
            modifiers = f" {modifiers}"

        declaration = f"{prefix}{field.access.value}{modifiers} {field.type_name} {field.name}"
        if field.default_value is not None:
            declaration += f" = {field.default_value}"
        declaration += ";"

        if field.comment:
            declaration += field.comment

        lines.append(declaration)

        return lines

    def _serialize_property(self, prop: CSharpProperty, indent: int) -> list[str]:
        """Serialize a property declaration."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Attributes
        for attr in prop.attributes:
            lines.append(f"{prefix}{attr.to_string()}")

        # Property declaration
        accessors = []
        if prop.has_getter:
            accessors.append("get")
        if prop.has_setter:
            accessors.append("set")
        accessor_str = "; ".join(accessors)

        declaration = f"{prefix}{prop.access.value} {prop.type_name} {prop.name} {{ {accessor_str}; }}"
        if prop.default_value is not None:
            declaration += f" = {prop.default_value};"

        if prop.comment:
            declaration += prop.comment

        lines.append(declaration)

        return lines

    def _serialize_constructor(self, constructor: CSharpConstructor, indent: int) -> list[str]:
        """Serialize a constructor declaration."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Parameter list
        params = ", ".join(f"{p.type_name} {p.name}" for p in constructor.parameters)

        # Constructor signature
        declaration = f"{prefix}{constructor.access.value} {constructor.class_name}({params})"

        # Base call
        if constructor.base_call_args:
            args_str = ", ".join(constructor.base_call_args)
            declaration += f": base({args_str})"

        lines.append(declaration)
        lines.append(f"{prefix}{{")

        # Body
        body_prefix = prefix + self.INDENT
        for stmt in constructor.body:
            lines.append(f"{body_prefix}{stmt}")

        lines.append(f"{prefix}}}")

        # Parameterless constructor
        if constructor.parameters:
            lines.append(f"{prefix}// Parameterless constructor for Unity editor and serialization")
            lines.append(f"{prefix}{constructor.access.value} {constructor.class_name}() {{ }}")

        lines.append("")

        return lines

    def _serialize_method(self, method: CSharpMethod, indent: int) -> list[str]:
        """Serialize a method declaration."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Modifiers
        modifiers = " ".join(m.value for m in method.modifiers)
        if modifiers:
            modifiers = f" {modifiers}"

        # Parameter list
        params = ", ".join(f"{p.type_name} {p.name}" for p in method.parameters)

        lines.append(f"{prefix}{method.access.value}{modifiers} {method.return_type} {method.name}({params})")
        lines.append(f"{prefix}{{")

        # Body
        body_prefix = prefix + self.INDENT
        for stmt in method.body:
            lines.append(f"{body_prefix}{stmt}")

        lines.append(f"{prefix}}}")
        lines.append("")

        return lines

    def _serialize_enum_simple(self, enum: CSharpEnum, indent: int) -> list[str]:
        """Serialize a simple enum (without converter)."""
        lines: list[str] = []
        prefix = self.INDENT * indent

        # Attributes
        for attr in enum.attributes:
            lines.append(f"{prefix}{attr.to_string()}")

        lines.append(f"{prefix}{enum.access.value} enum {enum.name}")
        lines.append(f"{prefix}{{")

        # Members
        member_prefix = prefix + self.INDENT
        for i, member in enumerate(enum.members):
            comma = "," if i < len(enum.members) - 1 else ""
            if member.value is not None:
                lines.append(f"{member_prefix}{member.name} = {member.value}{comma}")
            else:
                lines.append(f"{member_prefix}{member.name}{comma}")

        lines.append(f"{prefix}}}")
        lines.append("")

        return lines
