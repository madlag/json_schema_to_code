"""
Base class for code generation backends.

Defines the interface that all language-specific backends must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import jinja2

from ..analyzer.ir_nodes import IR, ClassDef, FieldDef, TypeKind, TypeRef
from ..config import CodeGeneratorConfig


class CodeBackend(ABC):
    """Abstract base class for code generation backends."""

    # Type mapping from schema types to language types
    TYPE_MAP: dict[str, str] = {}

    # Template directory name
    TEMPLATE_LANG: str = ""

    # File extension
    FILE_EXTENSION: str = ""

    def __init__(self, config: CodeGeneratorConfig):
        """
        Initialize the backend.

        Args:
            config: Code generation configuration
        """
        self.config = config
        self._setup_templates()

    def _setup_templates(self) -> None:
        """Set up Jinja2 templates."""
        template_dir = Path(__file__).parent.parent.parent / "templates" / self.TEMPLATE_LANG
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            lstrip_blocks=True,
            trim_blocks=True,
        )
        # Add custom filters
        self.jinja_env.filters["snake_to_pascal"] = self._snake_to_pascal

        self.prefix_template = self.jinja_env.get_template(f"prefix.{self.FILE_EXTENSION}.jinja2")
        self.class_template = self.jinja_env.get_template(f"class.{self.FILE_EXTENSION}.jinja2")
        self.suffix_template = self.jinja_env.get_template(f"suffix.{self.FILE_EXTENSION}.jinja2")

    @abstractmethod
    def generate(self, ir: IR) -> str:
        """
        Generate code from IR.

        Args:
            ir: The intermediate representation

        Returns:
            Generated code as a string
        """

    @abstractmethod
    def translate_type(self, type_ref: TypeRef) -> str:
        """
        Translate an IR type to a language-specific type string.

        Args:
            type_ref: The type reference

        Returns:
            Language-specific type string
        """

    @abstractmethod
    def format_default_value(self, value: Any, type_ref: TypeRef) -> str:
        """
        Format a default value for the target language.

        Args:
            value: The default value
            type_ref: The type of the value

        Returns:
            Formatted default value string
        """

    def _snake_to_pascal(self, text: str) -> str:
        """Convert snake_case to PascalCase."""
        import re

        words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text.replace("_", " ").replace("-", " "))
        return "".join(word.capitalize() for word in words if word)

    def _get_comment_prefix(self) -> str:
        """Get the comment prefix for the language."""
        return "#" if self.TEMPLATE_LANG == "python" else "//"

    def _prepare_class_context(self, class_def: ClassDef) -> dict[str, Any]:
        """
        Prepare the template context for a class.

        Args:
            class_def: The class definition

        Returns:
            Dictionary of template variables
        """
        # Order fields: required fields first, then optional fields with defaults
        ordered_fields = self._order_fields(class_def.fields)

        properties = {}
        for field in ordered_fields:
            field_ctx = self._prepare_field_context(field)
            properties[field.name] = field_ctx

        # Build base properties for constructor call
        base_properties = {}
        base_constructor_fields = []
        for field in class_def.base_fields:
            if field.is_const:
                if field.is_overridden_const:
                    # Overridden const - pass literal value
                    base_properties[f'"{field.default_value}"'] = self._prepare_field_context(field)
                else:
                    # Base class const (not overridden) - pass variable name
                    base_properties[field.name] = self._prepare_field_context(field)
                # Don't add const fields to constructor params
            else:
                # Regular property - pass variable name AND add to constructor for C#
                base_properties[field.name] = self._prepare_field_context(field)
                if self.TEMPLATE_LANG == "cs":
                    base_constructor_fields.append(field)

        # For C#, constructor includes base class parameters first, then this class's parameters
        # For Python, only this class's fields (inheritance works differently)
        constructor_fields = self._order_fields(class_def.constructor_fields)
        constructor_properties = {}

        # Add base class fields first (for C# only)
        for field in base_constructor_fields:
            field_ctx = self._prepare_field_context(field)
            constructor_properties[field.name] = field_ctx

        # Add this class's fields
        for field in constructor_fields:
            field_ctx = self._prepare_field_context(field)
            constructor_properties[field.name] = field_ctx

        # Determine the EXTENDS value
        extends = class_def.base_class
        if class_def.is_enum and class_def.enum_def and self.TEMPLATE_LANG == "python":
            # For Python enums, set base type (e.g., 'str' for string enums)
            if class_def.enum_def.value_type == "string":
                extends = "str"
            elif class_def.enum_def.value_type == "integer":
                extends = "int"

        return {
            "CLASS_NAME": class_def.name,
            "EXTENDS": extends,
            "SUB_CLASSES": class_def.subclasses,
            "IMPLEMENTS": class_def.implements,
            "INTERFACE_PROPERTIES": class_def.interface_properties,
            "properties": properties,
            "constructor_properties": constructor_properties,
            "BASE_PROPERTIES": base_properties,
            "enum": class_def.enum_def.members if class_def.is_enum and class_def.enum_def else {},
            "ENUM": class_def.is_enum and self.TEMPLATE_LANG == "cs",
            "validation_code": class_def.validation_code,
        }

    def _order_fields(self, fields: list[FieldDef]) -> list[FieldDef]:
        """
        Order fields for dataclass compatibility.

        For Python: Required fields (without defaults) must come before optional fields
        (with defaults).
        For C#: Keep original order (C# constructors handle this differently).
        """
        if self.TEMPLATE_LANG == "cs":
            # C# keeps original order
            return list(fields)

        required_fields = []
        optional_fields = []

        for field in fields:
            has_default = field.has_default
            is_nullable = field.type_ref and field.type_ref.is_nullable
            type_has_default = field.type_ref and field.type_ref.has_default
            is_optional_class = not field.is_required and field.type_ref and field.type_ref.kind == TypeKind.CLASS

            # A field needs a default if it has one explicitly, or is nullable, or type has default,
            # or is an optional CLASS type (will get default_factory)
            if has_default or is_nullable or type_has_default or is_optional_class:
                optional_fields.append(field)
            else:
                required_fields.append(field)

        return required_fields + optional_fields

    def _prepare_field_context(self, field: FieldDef) -> dict[str, Any]:
        """
        Prepare the template context for a field.

        Args:
            field: The field definition

        Returns:
            Dictionary of template variables
        """
        type_info: dict[str, Any] = {}

        if field.type_ref:
            type_str = self.translate_type(field.type_ref)
            type_info["type"] = type_str

            # Determine if we need a default value
            has_explicit_default = field.has_default or field.type_ref.has_default
            is_nullable = field.type_ref.is_nullable

            if has_explicit_default:
                default_val = field.default_value if field.has_default else field.type_ref.default_value

                # Special case: null default on $ref means auto-initialize
                # with default_factory (Python only)
                # This matches the original codegen.py behavior
                if default_val is None and self.TEMPLATE_LANG == "python" and field.type_ref.kind == TypeKind.CLASS:
                    clean_type = field.type_ref.name.strip('"')
                    type_info["init"] = f"field(default_factory=lambda: {clean_type}())"
                else:
                    type_info["init"] = self.format_default_value(default_val, field.type_ref)
            elif not field.is_required and self.TEMPLATE_LANG == "python" and field.type_ref.kind == TypeKind.CLASS:
                # Python: Optional CLASS types (from $ref) without explicit default
                # If nullable (T | None), use = None
                # If not nullable (just T), use field(default_factory=...)
                if is_nullable:
                    type_info["init"] = self.format_default_value(None, field.type_ref)
                else:
                    clean_type = field.type_ref.name.strip('"')
                    type_info["init"] = f"field(default_factory=lambda: {clean_type}())"
            elif is_nullable and self.TEMPLATE_LANG == "python":
                # Python: Nullable fields without explicit default get None
                type_info["init"] = self.format_default_value(None, field.type_ref)
            # C#: Don't add = null for nullable types, the ? suffix is enough

            if field.is_const:
                type_info["modifier"] = "const"

            if field.comment:
                type_info["comment"] = field.comment

        result = {"TYPE": type_info}

        if field.escaped_name:
            result["ESCAPED_PROPERTY_NAME"] = field.escaped_name

        if field.is_interface_property:
            result["IS_INTERFACE_PROPERTY"] = True
            result["INTERFACE_PROPERTY_NAME"] = field.interface_property_name

        return result
