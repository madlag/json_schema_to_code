"""
C# code generation backend.

Generates C# class code from IR.
"""

from __future__ import annotations

from typing import Any

from ..analyzer.ir_nodes import IR, ClassDef, TypeKind, TypeRef
from ..config import CodeGeneratorConfig
from .base import CodeBackend


class CSharpBackend(CodeBackend):
    """C# code generation backend."""

    TEMPLATE_LANG = "cs"
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
        # Map enum type name -> {json_value -> member_name}
        self.enum_value_to_member: dict[str, dict[Any, str]] = {}

    def generate(self, ir: IR) -> str:
        """Generate C# code from IR."""
        # Reset import tracking
        self.required_imports = {"System", "Newtonsoft.Json"}

        # Build enum value to member mapping for default value formatting
        self.enum_value_to_member = {}
        for class_def in ir.classes:
            if class_def.is_enum and class_def.enum_def:
                # members is {member_name: json_value}
                # We need {json_value: member_name}
                value_to_member = {v: k for k, v in class_def.enum_def.members.items()}
                self.enum_value_to_member[class_def.name] = value_to_member

        # Generate class content
        class_content = ""
        for class_def in ir.classes:
            # Track imports based on class features
            if class_def.subclasses:
                self.required_imports.add("JsonSubTypes")

            class_ctx = self._prepare_class_context(class_def)
            rendered = self.class_template.render(class_ctx)
            class_content += rendered + "\n"

        # Generate prefix with imports
        import_lines = sorted(self.required_imports)
        prefix = self.prefix_template.render(
            generation_comment=ir.generation_comment,
            required_imports=import_lines,
        )

        # Generate suffix
        suffix = self.suffix_template.render()

        return prefix + class_content + suffix

    def translate_type(self, type_ref: TypeRef) -> str:
        """Translate IR type to C# type string."""
        # Check for explicit type override first
        if type_ref.override_type_csharp:
            result = type_ref.override_type_csharp
        else:
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
            # For T | null, convert to T?
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
            # C# const uses the inferred type
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

        # Check if this is an enum type with a string value
        if isinstance(value, str):
            type_name = type_ref.name if type_ref else None
            if type_name and type_name in self.enum_value_to_member:
                # Look up the enum member name for this JSON value
                value_to_member = self.enum_value_to_member[type_name]
                if value in value_to_member:
                    member_name = value_to_member[value]
                    return f"{type_name}.{member_name}"
            # Regular string
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

        # Non-empty list
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

        # Non-empty dict
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

    def _prepare_class_context(self, class_def: ClassDef) -> dict[str, Any]:
        """Prepare class context with C#-specific handling."""
        ctx = super()._prepare_class_context(class_def)

        # Handle enum generation for C#
        if class_def.is_enum and class_def.enum_def:
            ctx["ENUM"] = True
            # Transform member names using snake_to_pascal_case (removes underscores)
            from ...utils import snake_to_pascal_case

            transformed_members = {snake_to_pascal_case(name): value for name, value in class_def.enum_def.members.items()}
            ctx["enum"] = transformed_members
            # Enum converter uses Dictionary<> so we need this import
            self.required_imports.add("System.Collections.Generic")

        return ctx
