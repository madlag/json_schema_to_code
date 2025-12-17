"""
Python code generation backend.

Generates Python dataclass code from IR.
"""

from __future__ import annotations

import collections
from typing import Any

from ..analyzer.ir_nodes import IR, TypeAlias, TypeKind, TypeRef
from ..config import CodeGeneratorConfig
from .base import CodeBackend


class PythonBackend(CodeBackend):
    """Python code generation backend."""

    TEMPLATE_LANG = "python"
    FILE_EXTENSION = "py"

    TYPE_MAP = {
        "integer": "int",
        "string": "str",
        "boolean": "bool",
        "number": "float",
        "null": "None",
        "object": "Any",
        "list": "list",
        "dict": "dict",
        "tuple": "tuple",
    }

    def __init__(self, config: CodeGeneratorConfig):
        super().__init__(config)
        self.python_imports: set[tuple[str, str]] = set()
        self.needs_re_import = False
        self.type_aliases: set[str] = set()  # Track type alias definitions

    def generate(self, ir: IR) -> str:
        """Generate Python code from IR."""
        # Reset import tracking
        self.python_imports = set()
        self.needs_re_import = False
        self.type_aliases = set()

        # Always include base imports
        self.python_imports.add(("dataclasses", "dataclass"))
        self.python_imports.add(("dataclasses_json", "dataclass_json"))

        # Add future annotations if configured
        if self.config.use_future_annotations:
            self.python_imports.add(("__future__", "annotations"))

        # Check if any class has subclasses (needs ABC import)
        for class_def in ir.classes:
            if class_def.subclasses:
                self.python_imports.add(("abc", "ABC"))
                break

        # Check if any class is an enum (needs Enum import)
        for class_def in ir.classes:
            if class_def.is_enum:
                self.python_imports.add(("enum", "Enum"))
                break

        # Check if any class has validation with patterns (needs re import)
        for class_def in ir.classes:
            for line in class_def.validation_code:
                if "re.match" in line or "re.fullmatch" in line:
                    self.needs_re_import = True
                    break

        # Generate class content
        class_content = ""
        for class_def in ir.classes:
            class_ctx = self._prepare_class_context(class_def)
            rendered = self.class_template.render(class_ctx)
            class_content += rendered + "\n\n"

        # Separate type aliases
        simple_aliases = []
        forward_aliases = []

        class_names = {c.name for c in ir.classes}

        # Add type aliases from IR
        for alias in ir.type_aliases:
            alias_str = self._format_type_alias(alias)
            # Check if alias references classes
            has_forward = any(name in alias_str for name in class_names)
            if has_forward:
                forward_aliases.append(alias_str)
            else:
                simple_aliases.append(alias_str)

        # Add type aliases created during type translation (e.g., NoneOrInt)
        for alias_def in self.type_aliases:
            # Check if alias references classes
            has_forward = any(name in alias_def for name in class_names)
            if has_forward:
                forward_aliases.append(alias_def)
            else:
                simple_aliases.append(alias_def)

        # Assemble imports
        import_lines = self._assemble_imports()

        # Generate prefix
        prefix = self.prefix_template.render(
            generation_comment=ir.generation_comment,
            required_imports=import_lines,
            type_aliases=sorted(simple_aliases),
        )

        # Generate suffix
        suffix = self.suffix_template.render()

        # Combine
        output = prefix + class_content

        # Add forward reference aliases after classes
        if forward_aliases:
            for alias in sorted(forward_aliases):
                output += alias + "\n"
            output += "\n"

        output += suffix

        return output

    def translate_type(self, type_ref: TypeRef) -> str:
        """Translate IR type to Python type string."""
        # Check for explicit type override first
        if type_ref.override_type_python:
            result = type_ref.override_type_python
            # Add required imports for common types in override
            if "dict[" in result.lower() or "dict " in result.lower():
                pass  # dict is builtin, no import needed
            if "Any" in result:
                self.python_imports.add(("typing", "Any"))
        else:
            result = self._translate_type_inner(type_ref)

        # Handle nullability
        if type_ref.is_nullable and not result.endswith(" | None"):
            result = f"{result} | None"

        # Handle quoting
        if type_ref.is_quoted:
            result = f'"{result}"'

        return result

    def _translate_type_inner(self, type_ref: TypeRef) -> str:
        """Inner type translation without nullable handling."""
        if type_ref.kind == TypeKind.PRIMITIVE:
            type_name = self.TYPE_MAP.get(type_ref.name, type_ref.name)
            if type_name == "Any":
                self.python_imports.add(("typing", "Any"))
            return type_name

        if type_ref.kind == TypeKind.CLASS:
            return type_ref.name

        if type_ref.kind == TypeKind.ANY:
            self.python_imports.add(("typing", "Any"))
            return "Any"

        if type_ref.kind == TypeKind.ARRAY:
            if type_ref.type_args:
                item_type = self.translate_type(type_ref.type_args[0])
                return f"list[{item_type}]"
            return "list"

        if type_ref.kind == TypeKind.TUPLE:
            if type_ref.type_args:
                item_types = ", ".join(self.translate_type(t) for t in type_ref.type_args)
                return f"tuple[{item_types}]"
            return "tuple"

        if type_ref.kind == TypeKind.UNION:
            types = [self.translate_type(t) for t in type_ref.type_args]
            sorted_types = sorted(types)
            union_string = " | ".join(sorted_types)

            # Check if we should use inline unions or type aliases
            if self.config.use_inline_unions:
                # Return inline union syntax directly
                return union_string

            # Create type alias for Python unions
            # Quote any types that aren't primitives for the alias name
            alias_parts = []
            for t in sorted_types:
                # Strip quotes and convert to PascalCase for alias name
                clean_t = t.strip('"') if t.startswith('"') else t
                # Remove 'None' suffix and capitalize first letter
                alias_parts.append(self._snake_to_pascal(clean_t.replace(" | ", "Or")))

            type_alias_name = "Or".join(alias_parts)

            # Add type alias definition
            self.type_aliases.add(f"{type_alias_name} = {union_string}")

            return type_alias_name

        if type_ref.kind == TypeKind.CONST:
            self.python_imports.add(("typing", "Literal"))
            formatted = self._format_literal_value(type_ref.const_value)
            return f"Literal[{formatted}]"

        if type_ref.kind == TypeKind.ENUM:
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)

        return "Any"

    def format_default_value(self, value: Any, type_ref: TypeRef) -> str:
        """Format a default value for Python."""
        if value is None:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return "field(default=None, metadata=config(exclude=lambda x: x is None))"
            return "None"

        if isinstance(value, bool):
            result = "True" if value else "False"
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return f"field(default={result}, metadata=config(exclude=lambda x: x is {result}))"
            return result

        if isinstance(value, str):
            escaped = value.replace('"', '\\"')
            formatted = f'"{escaped}"'
            # Wrap long strings
            if len(formatted) > 40:
                formatted = f"(\n        {formatted}\n    )"
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return f'field(default={formatted}, metadata=config(exclude=lambda x: x == "{escaped}"))'
            return formatted

        if isinstance(value, (int, float)):
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return f"field(default={value}, metadata=config(exclude=lambda x: x == {value}))"
            return str(value)

        if isinstance(value, list):
            return self._format_list_default(value)

        if isinstance(value, dict):
            return self._format_dict_default(value)

        return str(value)

    def _format_list_default(self, value: list) -> str:
        """Format a list default value."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses_json", "config"))
                return "field(default_factory=list, metadata=config(exclude=lambda x: len(x) == 0))"
            return "field(default_factory=list)"

        # Non-empty list
        items = []
        for item in value:
            if isinstance(item, str):
                items.append(f'"{item}"')
            else:
                items.append(str(item))
        content = "[" + ", ".join(items) + "]"

        if self.config.exclude_default_value_from_json:
            self.python_imports.add(("dataclasses_json", "config"))
            return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
        return f"field(default_factory=lambda: {content})"

    def _format_dict_default(self, value: dict) -> str:
        """Format a dict default value."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses_json", "config"))
                return "field(default_factory=dict, metadata=config(exclude=lambda x: len(x) == 0))"
            return "field(default_factory=dict)"

        # Non-empty dict
        items = []
        for k, v in value.items():
            key_str = f'"{k}"' if isinstance(k, str) else str(k)
            val_str = f'"{v}"' if isinstance(v, str) else str(v)
            items.append(f"{key_str}: {val_str}")
        content = "{" + ", ".join(items) + "}"

        if self.config.exclude_default_value_from_json:
            self.python_imports.add(("dataclasses_json", "config"))
            return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
        return f"field(default_factory=lambda: {content})"

    def _prepare_field_context(self, field) -> dict:
        """Override to add field import when using default_factory."""
        result = super()._prepare_field_context(field)

        # Check if we're using field() in the init value
        if "TYPE" in result and "init" in result["TYPE"]:
            init_value = result["TYPE"]["init"]
            if isinstance(init_value, str) and init_value.startswith("field("):
                self.python_imports.add(("dataclasses", "field"))

        return result

    def _format_literal_value(self, value: Any) -> str:
        """Format a value for Literal type."""
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _format_type_alias(self, alias: TypeAlias) -> str:
        """Format a type alias as Python code."""
        if alias.union_components:
            union_str = " | ".join(sorted(alias.union_components))
            return f"{alias.name} = {union_str}"
        return f"{alias.name} = Any"

    def _assemble_imports(self) -> list[str]:
        """Assemble Python import statements."""
        # Group imports by module
        import_groups: dict[str, set[str]] = collections.defaultdict(set)
        for module, name in self.python_imports:
            import_groups[module].add(name)

        # Define standard library modules
        STDLIB_MODULES = {"abc", "collections", "dataclasses", "enum", "typing", "re"}

        # Separate stdlib and third-party
        stdlib_groups = {m: import_groups[m] for m in import_groups if m in STDLIB_MODULES}
        third_party_groups = {m: import_groups[m] for m in import_groups if m not in STDLIB_MODULES and m != "__future__"}

        assembled = []

        # __future__ imports first
        if "__future__" in import_groups:
            names = sorted(import_groups["__future__"])
            assembled.append(f"from __future__ import {', '.join(names)}")
            if stdlib_groups or third_party_groups:
                assembled.append("")

        # re module import
        if self.needs_re_import:
            assembled.append("import re")

        # Standard library
        for module in sorted(stdlib_groups.keys()):
            names = sorted(stdlib_groups[module])
            assembled.append(f"from {module} import {', '.join(names)}")

        if stdlib_groups and third_party_groups:
            assembled.append("")

        # Third party
        for module in sorted(third_party_groups.keys()):
            names = sorted(third_party_groups[module])
            assembled.append(f"from {module} import {', '.join(names)}")

        return assembled
