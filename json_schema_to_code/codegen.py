import collections
import copy
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import jinja2

from . import __version__
from .cli_utils import reconstruct_command_line
from .utils import snake_to_pascal_case
from .validator import ValidationGenerator

CURRENT_DIR = Path(__file__).parent.resolve().absolute()


class ImportType(Enum):
    """Abstract import types that map to language-specific imports"""

    BASE = "base"  # The base import for the language, always needed
    LIST = "list"
    ANY = "any"
    LITERAL = "literal"
    TUPLE = "tuple"
    ENUM = "enum"
    SUB_CLASSES = "sub_classes"
    COLLECTIONS_GENERIC = "collections_generic"
    FUTURE_ANNOTATIONS = "future_annotations"
    FIELD = "field"  # dataclasses.field - only needed when using field() calls
    CONFIG = "config"  # dataclasses_json.config - only needed when using config() calls


class CodeGeneratorConfig:
    ignore_classes: list[str] = []
    global_ignore_fields: list[str] = []
    order_classes: list[str] = []
    ignoreSubClassOverrides: bool = False
    drop_min_max_items: bool = False
    use_array_of_super_type_for_variable_length_tuple: bool = True
    use_tuples: bool = True
    use_inline_unions: bool = False
    add_generation_comment: bool = True
    quoted_types_for_python: list[str] = []
    use_future_annotations: bool = True
    exclude_default_value_from_json: bool = False
    add_validation: bool = False
    # External reference import configuration for Python
    external_ref_base_module: str = ""  # Base module path for external $ref imports
    external_ref_schema_to_module: dict[str, str] = {}  # Custom schema path → module mappings

    @staticmethod
    def from_dict(d):
        config = CodeGeneratorConfig()
        for k, v in d.items():
            setattr(config, k, v)
        return config


class CodeGenerator:
    # C# reserved keywords that need escaping
    CS_RESERVED_KEYWORDS = {
        "abstract",
        "as",
        "base",
        "bool",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "checked",
        "class",
        "const",
        "continue",
        "decimal",
        "default",
        "delegate",
        "do",
        "double",
        "else",
        "enum",
        "event",
        "explicit",
        "extern",
        "false",
        "finally",
        "fixed",
        "float",
        "for",
        "foreach",
        "goto",
        "if",
        "implicit",
        "in",
        "int",
        "interface",
        "internal",
        "is",
        "lock",
        "long",
        "namespace",
        "new",
        "null",
        "object",
        "operator",
        "out",
        "override",
        "params",
        "private",
        "protected",
        "public",
        "readonly",
        "ref",
        "return",
        "sbyte",
        "sealed",
        "short",
        "sizeof",
        "stackalloc",
        "static",
        "string",
        "struct",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "uint",
        "ulong",
        "unchecked",
        "unsafe",
        "ushort",
        "using",
        "virtual",
        "void",
        "volatile",
        "while",
    }

    # Language-specific import mappings
    # None means the feature exists but requires no import
    PYTHON_IMPORT_MAP = {
        ImportType.LIST: None,
        ImportType.TUPLE: None,
        ImportType.BASE: [
            ("dataclasses", "dataclass"),
            ("dataclasses_json", "dataclass_json"),
        ],
        ImportType.FIELD: ("dataclasses", "field"),
        ImportType.CONFIG: ("dataclasses_json", "config"),
        ImportType.SUB_CLASSES: ("abc", "ABC"),
        ImportType.ANY: ("typing", "Any"),
        ImportType.LITERAL: ("typing", "Literal"),
        ImportType.ENUM: ("enum", "Enum"),
        ImportType.FUTURE_ANNOTATIONS: ("__future__", "annotations"),
    }

    CS_IMPORT_MAP = {
        ImportType.LIST: "System.Collections.Generic",
        ImportType.TUPLE: "System.Collections.Generic",
        ImportType.BASE: ["System", "Newtonsoft.Json"],
        ImportType.SUB_CLASSES: "JsonSubTypes",
        ImportType.ANY: None,
        ImportType.LITERAL: None,
        ImportType.ENUM: None,
    }

    # Language-specific default factory patterns for mutable defaults
    DEFAULT_FACTORY_PATTERNS = {
        "python": {
            "empty_list": "field(default_factory=list)",
            "empty_dict": "field(default_factory=dict)",
            "populated_list": "field(default_factory=lambda: {content})",
            "populated_dict": "field(default_factory=lambda: {content})",
        },
        "cs": {
            "empty_list": "new {type_name}()",
            "empty_dict": "new {type_name}()",
            "populated_list": "new {type_name} {{{content}}}",
            "populated_dict": "new {type_name} {{{content}}}",
        },
    }

    def __init__(self, class_name: str, schema: Dict[str, Any], config: CodeGeneratorConfig, language: str):
        self.class_name = class_name
        self.config = config
        self.language = language
        # Preprocess schema to handle enum member names (x-enum-members or auto-generate for C#)
        self.schema = self._preprocess_schema_for_enum_members(schema)
        # Build ref_class_name_mapping from x-ref-class-name annotations
        self.ref_class_name_mapping = self._build_ref_class_name_mapping(self.schema)
        self.jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)
        # Add custom filters
        self.jinja_env.filters["snake_to_pascal"] = snake_to_pascal_case
        language_to_extension = {"cs": "cs", "python": "py"}
        extension = language_to_extension[language]
        self.prefix = self.jinja_env.from_string(open(CURRENT_DIR / f"templates/{language}/prefix.{extension}.jinja2").read())
        self.class_model = self.jinja_env.from_string(open(CURRENT_DIR / f"templates/{language}/class.{extension}.jinja2").read())
        self.suffix = self.jinja_env.from_string(open(CURRENT_DIR / f"templates/{language}/suffix.{extension}.jinja2").read())

        # Initialize validation generator if validation is enabled
        self.validator = ValidationGenerator(language) if config.add_validation else None
        self.needs_re_import = False  # Track if we need 're' module for Python

        self.language_type_maps: dict[str, dict[str, str]] = {
            "cs": {
                "integer": "int",
                "string": "string",
                "boolean": "bool",
                "number": "float",
                "null": "null",
                "object": "object",
                "list": "List",
                "dict": "Dictionary",
                "tuple": "Tuple",
            },
            "python": {
                "integer": "int",
                "string": "str",
                "boolean": "bool",
                "number": "float",
                "null": "None",
                "object": "Any",
                "list": "list",
                "dict": "dict",
                "tuple": "tuple",
            },
        }
        if language not in self.language_type_maps:
            raise Exception("Language not supported: " + language)
        self.type_map = self.language_type_maps[language]

        self.language_type_brackets = {"cs": "<>", "python": "[]"}
        if language not in self.language_type_brackets:
            raise Exception("Language not supported: " + language)
        self.type_brackets = self.language_type_brackets[language]

        self.subclasses = collections.defaultdict(list)
        self.base_class = dict()
        self.class_info = dict()
        self.type_aliases = set()  # Track needed type aliases
        self.required_imports = set()  # Track required imports
        self.python_import_tuples = set()  # Track Python import tuples (module, name)

        # Register basic imports for C#
        self.register_import_needed(ImportType.BASE)

        # Register future annotations import if requested for Python
        if self.language == "python" and self.config.use_future_annotations:
            self.register_import_needed(ImportType.FUTURE_ANNOTATIONS)

    def _get_comment_prefix(self) -> str:
        """Get the appropriate comment prefix for the current language"""
        return "//" if self.language == "cs" else "#"

    @staticmethod
    def _is_external_ref(value: Any) -> bool:
        """Check if a value is an external $ref (not a local reference)."""
        return isinstance(value, dict) and "$ref" in value and not value["$ref"].startswith("#")

    def register_import_needed(self, import_type: ImportType) -> None:
        """Register that a specific import type is needed.

        Maps abstract import types to actual language-specific imports.

        Args:
            import_type: Abstract import type from ImportType enum

        Raises:
            ValueError: If the import_type is not supported for the current language
        """
        if self.language == "python":
            if import_type not in self.PYTHON_IMPORT_MAP:
                raise ValueError(f"Import type {import_type} is not supported for Python")
            import_specs = self.PYTHON_IMPORT_MAP[import_type]
            if import_specs is not None:  # None means no import needed
                # Handle both single tuple and list of tuples
                if isinstance(import_specs, tuple):
                    import_specs = [import_specs]
                for import_spec in import_specs:
                    self.python_import_tuples.add(import_spec)
        elif self.language == "cs":
            if import_type not in self.CS_IMPORT_MAP:
                raise ValueError(f"Import type {import_type} is not supported for C#")
            import_names = self.CS_IMPORT_MAP[import_type]
            if import_names is not None:  # None means no import needed
                # Handle both single string and list of strings
                if isinstance(import_names, str):
                    import_names = [import_names]
                for import_name in import_names:
                    self.required_imports.add(import_name)
        else:
            raise ValueError(f"Language '{self.language}' is not supported")

    def _create_default_factory_value(self, container_type: str, default_value, type_name: str | None = None) -> str:
        """
        Create a language-appropriate default factory value for mutable containers.

        Args:
            container_type: "list" or "dict"
            default_value: The default value (list or dict)
            type_name: Type name for languages that need it (like C#)

        Returns:
            String representing the default factory pattern
        """
        if self.language not in self.DEFAULT_FACTORY_PATTERNS:
            raise ValueError(f"Language '{self.language}' not supported for default factories")

        patterns = self.DEFAULT_FACTORY_PATTERNS[self.language]
        is_empty = len(default_value) == 0

        if container_type == "list":
            if is_empty:
                base_pattern = patterns["empty_list"].format(type_name=type_name)
                if self.config.exclude_default_value_from_json and self.language == "python":
                    self.register_import_needed(ImportType.FIELD)
                    self.register_import_needed(ImportType.CONFIG)
                    return "field(default_factory=list, metadata=config(exclude=lambda x: len(x) == 0))"
                # Register field import for the base pattern
                if self.language == "python":
                    self.register_import_needed(ImportType.FIELD)
                return base_pattern
            else:
                # Format list content
                formatted_items = []
                for item in default_value:
                    if isinstance(item, str):
                        formatted_items.append(f'"{item}"')
                    else:
                        formatted_items.append(str(item))
                if self.language == "python":
                    content = "[" + ", ".join(formatted_items) + "]"
                    if self.config.exclude_default_value_from_json:
                        self.register_import_needed(ImportType.FIELD)
                        self.register_import_needed(ImportType.CONFIG)
                        return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
                    # Register field import for the base pattern
                    self.register_import_needed(ImportType.FIELD)
                else:  # C# and other languages
                    content = ", ".join(formatted_items)
                return patterns["populated_list"].format(content=content, type_name=type_name)

        elif container_type == "dict":
            if is_empty:
                base_pattern = patterns["empty_dict"].format(type_name=type_name)
                if self.config.exclude_default_value_from_json and self.language == "python":
                    self.register_import_needed(ImportType.FIELD)
                    self.register_import_needed(ImportType.CONFIG)
                    return "field(default_factory=dict, metadata=config(exclude=lambda x: len(x) == 0))"
                # Register field import for the base pattern
                if self.language == "python":
                    self.register_import_needed(ImportType.FIELD)
                return base_pattern
            else:
                # Format dict content
                formatted_items = []
                for key, value in default_value.items():
                    if isinstance(key, str):
                        formatted_key = f'"{key}"'
                    else:
                        formatted_key = str(key)

                    if isinstance(value, str):
                        formatted_value = f'"{value}"'
                    else:
                        formatted_value = str(value)

                    if self.language == "python":
                        formatted_items.append(f"{formatted_key}: {formatted_value}")
                    elif self.language == "cs":
                        formatted_items.append(f"[{formatted_key}] = {formatted_value}")

                if self.language == "python":
                    content = "{" + ", ".join(formatted_items) + "}"
                    if self.config.exclude_default_value_from_json:
                        self.register_import_needed(ImportType.FIELD)
                        self.register_import_needed(ImportType.CONFIG)
                        return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
                    # Register field import for the base pattern
                    self.register_import_needed(ImportType.FIELD)
                else:
                    content = ", ".join(formatted_items)

                return patterns["populated_dict"].format(content=content, type_name=type_name)

        else:
            raise ValueError(f"Unsupported container type: {container_type}")

    def _assemble_python_imports(self) -> list[str]:
        """Assemble Python imports by grouping them by module and sorting"""
        if self.language != "python":
            return []

        # Group imports by module
        import_groups = collections.defaultdict(set)
        for module, name in self.python_import_tuples:
            import_groups[module].add(name)

        # Define standard library modules
        STDLIB_MODULES = {"abc", "collections", "dataclasses", "enum", "typing", "re"}

        # Separate stdlib and third-party imports
        stdlib_groups = {m: import_groups[m] for m in import_groups if m in STDLIB_MODULES}
        third_party_groups = {m: import_groups[m] for m in import_groups if m not in STDLIB_MODULES and m != "__future__"}

        # Assemble import statements - __future__ imports must come first
        assembled_imports = []

        # Handle __future__ imports first (they must be at the top)
        if "__future__" in import_groups:
            names = sorted(import_groups["__future__"])
            if len(names) == 1:
                assembled_imports.append(f"from __future__ import {names[0]}")
            else:
                assembled_imports.append(f"from __future__ import {', '.join(names)}")
            # Add blank line after __future__ imports if there are other imports
            if stdlib_groups or third_party_groups:
                assembled_imports.append("")

        # Handle standard library imports
        if stdlib_groups or self.needs_re_import:
            # Add 're' module import if needed (as module import, not from import)
            if self.needs_re_import:
                assembled_imports.append("import re")

            for module in sorted(stdlib_groups.keys()):
                names = sorted(stdlib_groups[module])
                if len(names) == 1:
                    assembled_imports.append(f"from {module} import {names[0]}")
                else:
                    assembled_imports.append(f"from {module} import {', '.join(names)}")
            # Add blank line after stdlib imports if there are third-party imports
            if third_party_groups:
                assembled_imports.append("")

        # Handle third-party imports
        if third_party_groups:
            for module in sorted(third_party_groups.keys()):
                names = sorted(third_party_groups[module])
                if len(names) == 1:
                    assembled_imports.append(f"from {module} import {names[0]}")
                else:
                    assembled_imports.append(f"from {module} import {', '.join(names)}")

        return assembled_imports

    def _generate_command_comment(self) -> str:
        """Generate a simplified command line comment for the generated file"""
        if not self.config.add_generation_comment:
            return ""

        # Use appropriate comment syntax for the language
        comment_prefix = self._get_comment_prefix()

        # Reconstruct command line using CLI utilities
        try:
            from .json_schema_to_code import json_schema_to_code as click_command  # noqa

            command_line = reconstruct_command_line(click_command)
        except (ImportError, AttributeError):
            # Fallback if Click command not available
            command_line = "json_schema_to_code"

        return f"{comment_prefix} Generated by json_schema_to_code v{__version__} : {command_line}"

    def optional_type(self, type: str) -> dict[str, str]:
        match self.language:
            case "python":
                t = type + " | None"
                if self.config.exclude_default_value_from_json:
                    init_value = self.format_field_with_metadata(None, t)
                else:
                    init_value = "None"
                return {"type": t, "init": init_value}
            case "cs":
                t = type + "?"
                return {"type": t}
            case _:
                raise Exception("Fix optional type for " + self.language)

    def union_type(self, types: list[str]) -> str:
        """Generate union type - either inline or type alias based on config"""
        sorted_types = sorted(types)

        match self.language:
            case "python":
                # Handle quoted types in unions properly
                has_quoted_types = any(t.startswith('"') and t.endswith('"') for t in sorted_types)

                if has_quoted_types:
                    # Unquote all types, create union, then quote the entire union
                    unquoted_types = [t.strip('"') if t.startswith('"') and t.endswith('"') else t for t in sorted_types]
                    union_type_string = " | ".join(unquoted_types)
                    quoted_union = f'"{union_type_string}"'
                else:
                    # Normal union without quotes
                    union_type_string = " | ".join(sorted_types)
                    quoted_union = union_type_string

                if self.config.use_inline_unions:
                    # Return inline union syntax
                    return quoted_union
                else:
                    # Generate and return type alias like "IntOrStr"
                    unquoted_for_alias = [t.strip('"') if t.startswith('"') and t.endswith('"') else t for t in sorted_types]
                    capitalized_types = [snake_to_pascal_case(t) for t in unquoted_for_alias]
                    type_alias_name = "Or".join(capitalized_types)

                    # Generate the type alias definition
                    type_alias_def = f"{type_alias_name} = {quoted_union}"
                    self.type_aliases.add(type_alias_def)

                    return type_alias_name
            case "cs":
                # Special case: T | null unions should be converted to nullable types T?
                null_type = self.type_map["null"]  # "null" for C#
                if len(sorted_types) == 2 and null_type in sorted_types:
                    # Extract the non-null type
                    non_null_types = [t for t in sorted_types if t != null_type]
                    if len(non_null_types) == 1:
                        # This is a T | null union, convert to nullable type T?
                        base_type = non_null_types[0]
                        return self.optional_type(base_type)["type"]

                if self.config.use_inline_unions:
                    # C# doesn't support inline unions, use object as fallback
                    union_types_str = " | ".join(sorted_types)
                    raise Exception(
                        f"C# code generation failed: Union types are not supported when 'use_inline_unions' is enabled.\n"
                        f"\n"
                        f"Union type encountered: {union_types_str}\n"
                        f"\n"
                        f"C# does not natively support inline union types (like Python's 'str | int').\n"
                        f"\n"
                        f"To fix this, you have two options:\n"
                        f"  1. Set 'use_inline_unions=False' in CodeGeneratorConfig - this will generate type aliases\n"
                        f"     (though they still resolve to 'object' in C#)\n"
                        f"  2. Refactor your JSON schema to avoid union types:\n"
                        f"     - Use discriminated unions with a 'type' discriminator field\n"
                        f"     - Split union properties into separate optional properties\n"
                        f"     - Use a base class with subclasses for different variants\n"
                        f"\n"
                        f"Note: Python dataclass generation fully supports union types, so this limitation\n"
                        f"only affects C# code generation."
                    )
                else:
                    # Generate type alias for C# (even though it's still object, keep the naming)
                    capitalized_types = [snake_to_pascal_case(t) for t in sorted_types]
                    type_alias_name = "Or".join(capitalized_types)

                    # For C#, type aliases still resolve to object but keep the naming
                    type_alias_def = f"// {type_alias_name} = object (union type)"
                    self.type_aliases.add(type_alias_def)

                    return type_alias_name
            case _:
                union_types_str = " | ".join(sorted_types)
                raise Exception(
                    f"Union types are not supported for language '{self.language}'.\n"
                    f"\n"
                    f"Union type encountered: {union_types_str}\n"
                    f"\n"
                    f"To fix this, refactor your JSON schema to avoid union types:\n"
                    f"  - Use discriminated unions with a 'type' discriminator field\n"
                    f"  - Split union properties into separate optional properties\n"
                    f"  - Use a base class with subclasses for different variants"
                )

    def const_type(self, t: Dict[str, Any]) -> Dict[str, Any]:
        match self.language:
            case "python":
                const = t["const"]
                self.register_import_needed(ImportType.LITERAL)
                formatted_const = self.format_default_value(const, "str")
                return {"type": f'Literal["{const}"]', "init": formatted_const}
            case "cs":
                # For C#, we need to infer the type from the const value if not provided
                const_value = t["const"]
                if "type" in t:
                    type_name = self.type_map[t["type"]]
                else:
                    # Infer type from the const value
                    if isinstance(const_value, str):
                        type_name = self.type_map["string"]
                    elif isinstance(const_value, int):
                        type_name = self.type_map["integer"]
                    elif isinstance(const_value, float):
                        type_name = self.type_map["number"]
                    elif isinstance(const_value, bool):
                        type_name = self.type_map["boolean"]
                    else:
                        type_name = "object"
                formatted_value = self.format_default_value(const_value, type_name)
                return {"type": type_name, "init": formatted_value, "modifier": "const"}
            case _:
                raise Exception("Fix const type for " + self.language)

    def quote_type(self, type: str) -> str:
        if self.language == "python" and type in self.config.quoted_types_for_python:
            return f'"{type}"'
        return type

    def _find_definition(self, name: str) -> tuple[str, dict] | None:
        """Find a definition by name, handling PascalCase mapping.

        Returns:
            Tuple of (original_name, definition_dict) or None if not found
        """
        definitions = self.schema.get("definitions") or self.schema.get("$defs")
        if not definitions:
            return None

        # Try original name first
        if name in definitions:
            return (name, definitions[name])

        # Try PascalCase name
        if hasattr(self, "definition_name_mapping"):
            # Reverse lookup: find original name from PascalCase name
            for orig_name, pascal_name in self.definition_name_mapping.items():
                if pascal_name == name and orig_name in definitions:
                    return (orig_name, definitions[orig_name])

        return None

    def _is_csharp_enum(self, def_info: dict) -> bool:
        """Check if a definition will be generated as a C# enum.

        A definition becomes a C# enum if:
        1. It has x-enum-members (custom member names), OR
        2. It has enum as a dict (preprocessed from x-enum-members) and type is "string"
        """
        if "x-enum-members" in def_info:
            return True
        enum_val = def_info.get("enum")
        return isinstance(enum_val, dict) and def_info.get("type") == "string"

    def _get_enum_type_name(self, enum_values: list) -> str:
        """Determine the type name for enum values.

        Raises:
            Exception: If enum values have mixed types
        """
        type_names = {type(e).__name__ for e in enum_values}
        if len(type_names) > 1:
            raise Exception("Enums with different types are not supported")

        type_name = type_names.pop()
        type_mapping = {"str": "string", "int": "integer", "float": "float"}
        return type_mapping.get(type_name, type_name)

    def _generate_enum_comment(self, enum_values: list) -> str:
        """Generate a comment listing allowed enum values."""
        comment_prefix = self._get_comment_prefix()
        values_str = ", ".join([f'"{e}"' for e in enum_values])
        return f"  {comment_prefix} Allowed values: {values_str}"

    def _handle_enum_type(self, type_info: dict) -> dict:
        """Handle enum type in translate_type."""
        enum_values = type_info["enum"]
        if isinstance(enum_values, dict):
            # Already preprocessed - get values from dict
            enum_values = list(enum_values.values())

        type_name = self._get_enum_type_name(enum_values)

        # For C# string enums, use string type directly (don't create a class)
        if self.language == "cs" and type_name == "string":
            return {"type": "string", "comment": self._generate_enum_comment(enum_values)}

        Warning(f"We should have information about what values are allowed for enum {type_name}")
        return {"type": self.type_map[type_name], "comment": self._generate_enum_comment(enum_values)}

    def ref_type(self, ref: str) -> str:
        """Resolve a $ref to its class name.

        PRIORITY: Always use the $def key name from definition_name_mapping.
        Never use inline class names or field-name-based naming for $ref items.
        """
        # Handle external $ref: extract class name from fragment
        if not ref.startswith("#") and "#/$defs/" in ref:
            type_name = ref.split("#/$defs/", 1)[1]
        else:
            type_name = ref.split("/")[-1]

        # Check for x-ref-class-name mapping in schema (for external $ref)
        if hasattr(self, "ref_class_name_mapping"):
            if type_name in self.ref_class_name_mapping:
                type_name = self.ref_class_name_mapping[type_name]
            elif type_name.endswith(".json") and type_name[:-5] in self.ref_class_name_mapping:
                type_name = self.ref_class_name_mapping[type_name[:-5]]

        # PRIORITY: Convert to PascalCase using definition_name_mapping (the $def key name)
        # This ensures $def keys are always used, never field-name-based names
        original_type_name = type_name
        if hasattr(self, "definition_name_mapping") and type_name in self.definition_name_mapping:
            type_name = self.definition_name_mapping[type_name]
            # $def name found - use it and continue processing (enums, quoting, etc.)
        else:
            # Not a $def reference - might be external $ref or enum
            # Still process it but don't use inline class names
            pass

        # For C#, check if this is a string enum
        if self.language == "cs":
            def_result = self._find_definition(original_type_name)
            if def_result:
                _, def_info = def_result
                if isinstance(def_info, dict):
                    if self._is_csharp_enum(def_info):
                        # Return the enum class name (PascalCase version)
                        return type_name
                    # String enum without x-enum-members -> use "string" type
                    if def_info.get("type") == "string" and "enum" in def_info:
                        return "string"

        # For Python, quote types that are in the quoted_types_for_python list
        type_name = self.quote_type(type_name)

        return type_name

    def _schema_ref_to_module_path(self, schema_ref: str) -> tuple[str, str] | None:
        """Convert external $ref to (module_path, class_name) for Python imports.

        Example:
            "/activities/guess/guess_schema#/$defs/GuessData"
            → ("explayn_dh_agent.barbara.db.app_object_definitions.activities.guess.guess_dataclass", "GuessData")

        Args:
            schema_ref: The $ref string from schema

        Returns:
            (module_path, class_name) tuple or None if not an external ref or not configured
        """
        if not schema_ref or schema_ref.startswith("#"):
            return None  # Local ref, not external

        # Parse: "/activities/guess/guess_schema#/$defs/GuessData"
        if "#/$defs/" not in schema_ref:
            return None

        path_part, class_name = schema_ref.split("#/$defs/", 1)
        path_part = path_part.lstrip("/")

        # Check for custom mapping first
        if self.config.external_ref_schema_to_module:
            if path_part in self.config.external_ref_schema_to_module:
                module_path = self.config.external_ref_schema_to_module[path_part]
                return (module_path, class_name)

        # Auto-convert using base module if configured
        if self.config.external_ref_base_module:
            # Convert: "activities/guess/guess_schema" → "activities.guess.guess_dataclass"
            module_path = path_part.replace("/", ".").replace("_schema", "_dataclass")
            full_module = f"{self.config.external_ref_base_module}.{module_path}"
            return (full_module, class_name)

        return None

    def super_type(self, items: Dict[str, Any]):
        types = set()
        for item in items:
            if "type" in item:
                if isinstance(item["type"], list):  # type: ignore
                    for t in item["type"]:  # type: ignore
                        types.add(t)
                elif isinstance(item["type"], str):  # type: ignore
                    types.add(item["type"])  # type: ignore
            else:
                raise Exception("Unknown type " + str(item))
        types = list(types)
        types.sort()
        return {"type": types}

    def _handle_union_type_with_defaults(self, type_info, union_key: str, field_name: str, is_required: bool) -> dict:
        """Helper method to handle oneOf/anyOf types with proper default value handling"""
        types = [self.translate_type(t, f"{field_name}_union", is_required=True)["type"] for t in type_info[union_key]]
        result = {"type": self.union_type(types)}

        # Handle default values for union types
        if "default" in type_info:
            result["init"] = self.format_field_with_metadata(type_info["default"], result["type"])
        elif not is_required:
            # Property is not required and has no default - make it nullable if not already
            # Check if None/null is already in the union
            none_type = self.type_map["null"]
            if none_type not in types:
                return self.optional_type(result["type"])
        return result

    def format_default_value(self, default_value, type_name: str) -> str:
        """Format a default value according to the target language"""
        if default_value is None:
            match self.language:
                case "python":
                    return "None"
                case "cs":
                    return "null"
                case _:
                    return "null"

        if isinstance(default_value, bool):
            match self.language:
                case "python":
                    return "True" if default_value else "False"
                case "cs":
                    return "true" if default_value else "false"
                case _:
                    return "true" if default_value else "false"

        if isinstance(default_value, str):
            # Escape quotes in the string
            escaped_value = default_value.replace('"', '\\"')
            formatted_string = f'"{escaped_value}"'

            # For Python, wrap long strings across multiple lines
            # Use a threshold of 40 characters for when to wrap to avoid long lines
            if self.language == "python" and len(formatted_string) > 40:
                return f"(\n        {formatted_string}\n    )"

            return formatted_string

        if isinstance(default_value, (int, float)):
            return str(default_value)

        if isinstance(default_value, list):
            return self._create_default_factory_value("list", default_value, type_name)

        if isinstance(default_value, dict):
            return self._create_default_factory_value("dict", default_value, type_name)

        # Fallback for other types
        return str(default_value)

    def format_field_with_metadata(self, default_value, type_name: str) -> str:
        """Format a field definition with metadata for dataclasses-json exclude functionality"""
        if self.language != "python" or not self.config.exclude_default_value_from_json:
            return self.format_default_value(default_value, type_name)

        # Create the exclude lambda based on the default value
        if default_value is None:
            exclude_condition = "x is None"
        elif isinstance(default_value, str):
            # Escape quotes in the string for the lambda
            escaped_value = default_value.replace('"', '\\"')
            exclude_condition = f'x == "{escaped_value}"'
        elif isinstance(default_value, bool):
            exclude_condition = f"x is {str(default_value)}"
        elif isinstance(default_value, (int, float)):
            exclude_condition = f"x == {default_value}"
        elif isinstance(default_value, list):
            # For lists, use the factory pattern with metadata
            return self._create_default_factory_value("list", default_value, type_name)
        elif isinstance(default_value, dict):
            # For dicts, use the factory pattern with metadata
            return self._create_default_factory_value("dict", default_value, type_name)
        else:
            exclude_condition = f"x == {default_value}"

        # For simple types, use field with default and metadata
        formatted_default = self.format_default_value(default_value, type_name)
        self.register_import_needed(ImportType.FIELD)
        self.register_import_needed(ImportType.CONFIG)
        return f"field(default={formatted_default}, metadata=config(exclude=lambda x: {exclude_condition}))"

    def translate_type(self, type_info, field_name, is_required=True):
        """
        Translate type information from JSON schema to target language type.

        Args:
            type_info: JSON schema type information
            field_name: Name of the field being processed (used for inline object naming)
            is_required: Whether this property is required (affects nullability)
        """
        if "$ref" in type_info:
            # Always use $def name for $ref items - never use inline class names
            # This ensures $def keys are prioritized over any field-name-based naming
            ref = type_info["$ref"]
            type = self.ref_type(ref)

            # Register import for external refs in Python
            if self.language == "python":
                module_info = self._schema_ref_to_module_path(ref)
                if module_info:
                    module_path, ref_class_name = module_info
                    self.python_import_tuples.add((module_path, ref_class_name))

            # Handle defaults and optional fields for $ref types
            result = {"type": type}
            if "default" in type_info:
                # Special case: null default on $ref means auto-initialize with default_factory
                if type_info["default"] is None and self.language == "python":
                    clean_type = type.strip('"')
                    self.register_import_needed(ImportType.FIELD)
                    # Use lambda to avoid type checker issues with forward references
                    result["init"] = f"field(default_factory=lambda: {clean_type}())"
                else:
                    # If there's an explicit non-null default value, use it
                    # For C# enums, convert string defaults to enum values
                    default_value = type_info["default"]
                    if self.language == "cs" and isinstance(default_value, str):
                        type_name = type.strip('"')
                        ref_name = type_info["$ref"].split("/")[-1]
                        def_result = self._find_definition(ref_name)
                        if def_result:
                            _, def_info = def_result
                            if self._is_csharp_enum(def_info):
                                # Find the enum member name for this JSON value
                                enum_dict = def_info.get("enum")
                                if isinstance(enum_dict, dict):
                                    # Preprocessed enum dict: {member_name: json_value}
                                    for member_name, json_value in enum_dict.items():
                                        if json_value == default_value:
                                            result["init"] = f"{type_name}.{member_name}"
                                            return result
                                elif "x-enum-members" in def_info:
                                    # Not yet preprocessed: {json_value: member_name}
                                    enum_members = def_info["x-enum-members"]
                                    member_name = enum_members.get(default_value)
                                    if member_name:
                                        result["init"] = f"{type_name}.{member_name}"
                                        return result

                    result["init"] = self.format_field_with_metadata(default_value, type)
            elif not is_required:
                # For optional $ref fields, use field(default_factory=lambda: ClassName())
                # This allows the field to be omitted and auto-initialized
                # Use lambda to avoid type checker issues with forward references
                if self.language == "python":
                    # Remove quotes from type name for default_factory
                    clean_type = type.strip('"')
                    self.register_import_needed(ImportType.FIELD)
                    result["init"] = f"field(default_factory=lambda: {clean_type}())"
                else:
                    # For other languages, make it nullable
                    return self.optional_type(type)
            return result
        elif "type" in type_info:
            type = type_info["type"]
            list_type = self.type_map["list"]
            tuple_type = self.type_map["tuple"]
            if type == "array":
                if isinstance(type_info["items"], dict):
                    item_type_info = self.translate_type(type_info["items"], field_name, is_required=True)  # Array items are always considered required
                    item_type = item_type_info["type"]
                    item_type = self.quote_type(item_type)
                    self.register_import_needed(ImportType.LIST)
                    type = f"{list_type}{self.type_brackets[0]}{item_type}{self.type_brackets[1]}"

                    # Handle default values for arrays
                    result = {"type": type}
                    if "default" in type_info:
                        result["init"] = self.format_field_with_metadata(type_info["default"], type)
                    elif not is_required:
                        # Array property is not required and has no default - make it nullable
                        return self.optional_type(type)
                    return result
                elif isinstance(type_info["items"], list):
                    if type_info.get("minItems") != type_info.get("maxItems"):
                        if not self.config.drop_min_max_items:
                            raise Exception("Variable length tuple is not supported")

                    if type_info.get("minItems") != type_info.get("maxItems") or not self.config.use_tuples:
                        if not self.config.use_array_of_super_type_for_variable_length_tuple:
                            # Check if all items are of the same type
                            item_types = [self.translate_type(t, field_name, is_required=True)["type"] for t in type_info["items"]]

                            for item_type in item_types[1:]:
                                # Items are not of the same type
                                if item_type != item_types[0]:
                                    raise Exception("The items are not of the same type: " + str(item_types))
                        item_type = self.super_type(type_info["items"])
                        item_type = self.translate_type(item_type, field_name, is_required=True)
                        self.register_import_needed(ImportType.LIST)
                        type = f"{list_type}{self.type_brackets[0]}{item_type['type']}{self.type_brackets[1]}"
                    elif self.config.use_tuples:
                        item_types = [self.translate_type(t, field_name, is_required=True)["type"] for t in type_info["items"]]
                        self.register_import_needed(ImportType.TUPLE)
                        type = f"{tuple_type}{self.type_brackets[0]}{', '.join(item_types)}{self.type_brackets[1]}"

                else:
                    raise Exception("Unknown type " + str(type_info["items"]))
            elif isinstance(type, list):
                nullable = False
                if "null" in type:
                    nullable = True
                    type.remove("null")

                if len(type) == 1:
                    base_type = self.translate_type({"type": type[0]}, f"{field_name}_union", is_required=True)["type"]
                    if nullable:
                        result = self.optional_type(base_type)
                        # Handle default values for nullable types
                        if "default" in type_info:
                            result["init"] = self.format_field_with_metadata(type_info["default"], result["type"])
                        return result
                    else:
                        result = {"type": base_type}
                        if "default" in type_info:
                            result["init"] = self.format_field_with_metadata(type_info["default"], base_type)
                        elif not is_required:
                            # Property is not required and has no default - make it nullable
                            return self.optional_type(base_type)
                        return result
                else:
                    # Use union_type for consistent logic
                    typeNames = [self.translate_type({"type": t}, f"{field_name}_union", is_required=True)["type"] for t in type]
                    type = self.union_type(typeNames)
            else:
                # Handle inline objects with properties
                if type == "object" and "properties" in type_info:
                    return self._handle_inline_object(type_info, field_name, is_required)

                t = self.type_map[str(type)]

                # Track Any import
                if t == "Any":
                    self.register_import_needed(ImportType.ANY)

                if "const" in type_info:
                    return self.const_type(type_info)

                # Handle default values for basic types
                result = {"type": t}
                if "default" in type_info:
                    result["init"] = self.format_field_with_metadata(type_info["default"], t)
                elif not is_required:
                    # Property is not required and has no default - make it nullable
                    return self.optional_type(t)
                return result
        elif "const" in type_info:
            return self.const_type(type_info)
        elif "enum" in type_info:
            return self._handle_enum_type(type_info)
        elif "oneOf" in type_info or "anyOf" in type_info:
            union_key = "oneOf" if "oneOf" in type_info else "anyOf"
            return self._handle_union_type_with_defaults(type_info, union_key, field_name, is_required)
        else:
            raise Exception("Unknown type " + str(type_info))

        # Handle default values for other types (like $ref)
        result = {"type": type}
        if "default" in type_info:
            result["init"] = self.format_field_with_metadata(type_info["default"], type)
        elif not is_required:
            # Property is not required and has no default - make it nullable
            return self.optional_type(type)
        return result

    def convert_message_class_to_json_name(self, properties, class_name):
        if "type" in properties:
            if "const" in properties["type"]:
                return properties["type"]["const"]
        return class_name

    def _to_csharp_enum_member_name(self, name: str) -> str:
        """Convert a name to PascalCase C# enum member name.

        Examples:
            "FULL" -> "Full"
            "FIRST_3_ROWS" -> "First3Rows"
            "NORMAL" -> "Normal"
            "Full" -> "Full" (already PascalCase)

        Args:
            name: The name to convert (from x-enum-members or enum value)

        Returns:
            PascalCase C# identifier
        """
        if not name:
            return "Value"
        return snake_to_pascal_case(name)

    def _preprocess_schema_for_enum_members(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess schema to transform enum arrays into dicts with PascalCase member names.

        For C#: If a schema definition has "enum" (array), transform it into a dict mapping
        PascalCase member names to JSON values. If x-enum-members is present, use those
        names; otherwise, auto-generate PascalCase names from the enum values.

        For Python: Only transform if x-enum-members is present (keep original behavior).

        Args:
            schema: The JSON schema dict

        Returns:
            Preprocessed schema with enum transformations applied
        """

        def process_value(value: Any) -> Any:
            """Recursively process values in the schema."""
            if isinstance(value, dict):
                return process_dict(value)
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            else:
                return value

        def process_dict(obj: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively process dicts in the schema."""
            result = {}
            for key, value in obj.items():
                # Check if this dict has enum array
                if key == "enum" and isinstance(value, list):
                    enum_array = value
                    enum_dict = {}

                    if "x-enum-members" in obj:
                        # Use x-enum-members values, convert to PascalCase for C#
                        enum_members = obj["x-enum-members"]
                        for enum_value in enum_array:
                            member_name = enum_members.get(enum_value, str(enum_value))
                            if self.language == "cs":
                                member_name = self._to_csharp_enum_member_name(member_name)
                            enum_dict[member_name] = enum_value
                    elif self.language == "cs":
                        # For C# without x-enum-members, auto-generate PascalCase from enum values
                        for enum_value in enum_array:
                            member_name = self._to_csharp_enum_member_name(str(enum_value))
                            enum_dict[member_name] = enum_value
                    else:
                        # For Python and other languages, keep enum as array
                        result[key] = value
                        continue

                    result[key] = enum_dict
                elif key == "x-enum-members":
                    # Remove x-enum-members after processing enum (if we used it)
                    # Only remove if enum was also present and processed
                    if "enum" not in obj or not isinstance(obj["enum"], list):
                        result[key] = process_value(value)
                    # Otherwise, skip it (already processed with enum)
                else:
                    result[key] = process_value(value)
            return result

        return process_dict(schema)

    def _build_ref_class_name_mapping(self, schema: Dict[str, Any]) -> Dict[str, str]:
        """Build mapping from $ref type names to class names using x-ref-class-name annotations.

        Recursively searches the schema for properties with $ref and x-ref-class-name,
        and builds a mapping from the $ref filename/type to the class name.
        """
        mapping = {}

        def process_dict(obj: Dict[str, Any]) -> None:
            """Recursively process dicts to find x-ref-class-name annotations."""
            if isinstance(obj, dict):
                # Check if this is a property with $ref and x-ref-class-name
                if "$ref" in obj and "x-ref-class-name" in obj:
                    ref_path = obj["$ref"]
                    # Extract the type name from the $ref (last part of path)
                    type_name = ref_path.split("/")[-1]
                    # Remove .json extension if present
                    if type_name.endswith(".json"):
                        type_name = type_name[:-5]
                    class_name = obj["x-ref-class-name"]
                    mapping[type_name] = class_name

                # Recursively process all values
                for value in obj.values():
                    if isinstance(value, dict):
                        process_dict(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                process_dict(item)

        process_dict(schema)
        return mapping

    def preprocess(self, class_name, info):
        p = copy.deepcopy(info)
        if "allOf" in p:
            allOf = p["allOf"]
            base_class = self.ref_type(allOf[0]["$ref"])
            # Change class_name camelcase to snake_case
            json_name = self.convert_message_class_to_json_name(allOf[1].get("properties", {}), class_name)
            if class_name not in self.config.ignore_classes:
                self.subclasses[base_class].append([class_name, json_name])
            self.base_class[class_name] = base_class

        # For C#, detect discriminated unions (anyOf/oneOf with type discriminator)
        if self.language == "cs":
            union_key = self._get_union_key(p)
            if union_key:
                discriminator_info = self._is_discriminated_union(union_key, p)
                if discriminator_info:
                    for variant_class, discriminator_value in discriminator_info:
                        self.subclasses[class_name].append([variant_class, discriminator_value])
                        self.base_class[variant_class] = class_name
                    # Store empty base class info for subclasses to inherit from
                    p = {"properties": {}}

        self.class_info[class_name] = p

    def prepare_class_info(self, class_name, info):
        """Wrapper function that catches exceptions and adds class name context"""
        try:
            return self._prepare_class_info(class_name, info)
        except Exception as e:
            raise Exception(f"Error processing class '{class_name}': {str(e)}") from e

    def _is_builtin_type(self, type_name: str) -> bool:
        """Check if a type is a built-in language type."""
        builtin_types = {"str", "int", "float", "bool", "None", "Any", "object", "string"}
        return type_name in builtin_types

    def _get_union_key(self, p: dict) -> str | None:
        """Get the union key ('oneOf' or 'anyOf') if present."""
        if "oneOf" in p:
            return "oneOf"
        if "anyOf" in p:
            return "anyOf"
        return None

    def _get_discriminator_value(self, ref: str) -> str | None:
        """Get the discriminator value from a referenced type's 'type' field with const."""
        def_name = ref.split("/")[-1]
        result = self._find_definition(def_name)
        if result is None:
            return None
        _, def_info = result
        return def_info.get("properties", {}).get("type", {}).get("const")

    def _is_discriminated_union(self, union_key: str, p: dict) -> list[tuple[str, str]] | None:
        """Check if a oneOf/anyOf is a discriminated union with 'type' field discriminator.

        Returns a list of (class_name, discriminator_value) tuples if discriminated,
        otherwise returns None.
        """
        items = p.get(union_key, [])
        if not items or not all("$ref" in item for item in items):
            return None

        discriminator_info = []
        for item in items:
            ref = item["$ref"]
            class_name = self.ref_type(ref)
            discriminator_value = self._get_discriminator_value(ref)
            if discriminator_value is None:
                return None
            discriminator_info.append((class_name, discriminator_value))

        return discriminator_info

    def _handle_oneof_type_alias(self, class_name: str, p: dict) -> dict | None:
        """Handle oneOf/anyOf with multiple $ref.

        For Python: creates a type alias (union type).
        For C#: if discriminated union, creates a base class with subclasses.
        """
        union_key = self._get_union_key(p)
        if not union_key:
            return p

        items = p[union_key]
        if not all("$ref" in item for item in items) or len(items) <= 1:
            return p

        union_types = [self.ref_type(item["$ref"]) for item in items]

        # For C#, check if this is a discriminated union (already registered in preprocess)
        if self.language == "cs" and self.subclasses.get(class_name):
            # Return empty base class for the union
            return {"properties": {}, "CLASS_NAME": class_name}

        # For Python (or non-discriminated unions), create type alias
        if self.config.use_inline_unions:
            union_string = " | ".join(sorted(union_types))
            if any(t.startswith('"') and t.endswith('"') for t in union_types):
                unquoted = [t.strip('"') if t.startswith('"') and t.endswith('"') else t for t in union_types]
                union_string = f'"{ " | ".join(sorted(unquoted)) }"'
            self.type_aliases.add(f"{class_name} = {union_string}")
        else:
            union_type_name = self.union_type(union_types)
            for alias in list(self.type_aliases):
                if alias.startswith(union_type_name + " ="):
                    self.type_aliases.remove(alias)
                    union_string = alias.split(" = ", 1)[1]
                    self.type_aliases.add(f"{class_name} = {union_string}")
                    break

        return None

    def _handle_base_type_or_enum(self, class_name: str, p: dict) -> dict | None:
        """Handle anyOf/oneOf or non-object types, including C# enum detection."""
        has_union = "anyOf" in p or "oneOf" in p
        is_non_object = "type" in p and p["type"] != "object"

        if not (has_union or is_non_object):
            return p

        base_type = self.translate_type(p, f"{class_name}_base", is_required=True)["type"]

        # For C# string enums, check if we should generate as enum
        if self.language == "cs" and "enum" in p and base_type == "string":
            if isinstance(p.get("enum"), dict) and len(p["enum"]) > 0:
                p["ENUM"] = True
                return p
            return None  # Skip class generation, use string type

        # Not an enum - set EXTENDS normally
        p["EXTENDS"] = base_type
        self.base_class[class_name] = base_type

        if base_type not in self.class_info and not self._is_builtin_type(base_type):
            self.class_info[base_type] = {"properties": {}}

        return p

    def _prepare_class_info(self, class_name, info):
        # Set the current parent context for inline object naming
        self._current_parent_context = class_name
        p = copy.deepcopy(info)

        if "allOf" in p:
            ref = p["allOf"][0]["$ref"]
            extends = self.ref_type(ref)

            # Register import for external refs in Python
            if self.language == "python":
                module_info = self._schema_ref_to_module_path(ref)
                if module_info:
                    module_path, base_class_name = module_info
                    self.python_import_tuples.add((module_path, base_class_name))

            p = p["allOf"][1]
            p["EXTENDS"] = extends

        # Check if this class was registered as a subclass of a discriminated union
        if class_name in self.base_class and "EXTENDS" not in p:
            p["EXTENDS"] = self.base_class[class_name]

        # Check if this is a oneOf with multiple $ref - create type alias instead of class
        p = self._handle_oneof_type_alias(class_name, p)
        if p is None:
            return None

        # Handle anyOf/oneOf at class level or non-object types
        p = self._handle_base_type_or_enum(class_name, p)
        if p is None:
            return None

        p["CLASS_NAME"] = class_name
        p["SUB_CLASSES"] = self.subclasses.get(class_name, [])

        # Track imports
        if p["SUB_CLASSES"]:
            self.register_import_needed(ImportType.SUB_CLASSES)
        if "enum" in p and p["enum"]:
            self.register_import_needed(ImportType.ENUM)

        properties = p.get("properties", {})

        # Handle x-csharp-implements annotation for C# interface implementation
        self._setup_csharp_interface_properties(p, properties)

        # Process properties (with or without inheritance)
        if p.get("EXTENDS") is not None:
            constructor_properties = self._process_base_properties(class_name, p)
            p_base = self._get_base_class_info(class_name)
            constructor_properties.update(self._process_class_properties(p, properties, p_base))
            # Filter out const fields from constructor_properties
            p["constructor_properties"] = {k: v for k, v in constructor_properties.items() if not (v.get("TYPE", {}).get("modifier") == "const")}
        else:
            p["constructor_properties"] = properties
            self._process_class_properties(p, properties)

        # Normalize enum format (for Python, enums may still be arrays)
        if "enum" in p:
            if not isinstance(p["enum"], dict):
                # For Python, convert to uppercase keys; for C#, should already be dict from preprocessing
                if self.language == "python":
                    p["enum"] = {k.upper(): k for k in p["enum"]}
                else:
                    # For C#, enums should have been preprocessed to dicts
                    # If not, auto-generate PascalCase names
                    p["enum"] = {self._to_csharp_enum_member_name(str(k)): k for k in p["enum"]}
        else:
            p["enum"] = {}

        if "properties" in p:
            p["properties"] = {k: v for k, v in p["properties"].items() if k not in self.config.global_ignore_fields}
        else:
            p["properties"] = {}

        # Escape C# reserved keywords and mark interface properties
        if self.language == "cs":
            self._escape_csharp_property_names(p)
            self._mark_interface_properties(p)

        if "constructor_properties" in p:
            # Filter out const fields and ignored fields from constructor_properties
            p["constructor_properties"] = {k: v for k, v in p["constructor_properties"].items() if k not in self.config.global_ignore_fields and not (v.get("TYPE", {}).get("modifier") == "const")}

        # Generate validation code if enabled
        if self.config.add_validation and self.validator:
            validation_code = self._generate_validation_code(p, class_name)
            p["validation_code"] = validation_code

        return p

    def _process_property_type(self, property_info: dict, property_name: str, is_required: bool) -> dict:
        """Process a single property's type information."""
        TYPE = self.translate_type(property_info, property_name, is_required=is_required)
        if "TYPE" not in property_info:
            property_info["TYPE"] = {}
        property_info["TYPE"].update(TYPE)
        return TYPE

    def _get_base_class_info(self, class_name: str) -> dict:
        """Get base class info, handling built-in types and external references."""
        if class_name not in self.base_class:
            # This class doesn't have a base class (might be external ref or root class)
            # Return empty properties
            return {"properties": {}}
        bc = self.base_class[class_name]
        if bc not in self.class_info:
            # External base class (from another schema) or built-in type
            # Return empty properties - inheritance will work at runtime via imports
            return {"properties": {}}
        result = self.class_info.get(bc)
        if result is None:
            raise Exception(f"Base class {bc} info is None for class {class_name}")
        return result

    def _process_base_properties(self, class_name: str, p: dict) -> dict:
        """Process properties from base class."""
        p["BASE_PROPERTIES"] = {}
        p_base = self._get_base_class_info(class_name)
        base_required = p_base.get("required", [])
        constructor_properties = {}

        for property, property_info in p_base["properties"].items():
            is_required = property in base_required
            self._process_property_type(property_info, property, is_required)

            child_property_info = p.get("properties", {}).get(property)
            if child_property_info is not None and "const" in child_property_info:
                p["BASE_PROPERTIES"][f'"{child_property_info["const"]}"'] = property_info
            else:
                constructor_properties[property] = property_info
                p["BASE_PROPERTIES"][property] = property_info

        return constructor_properties

    def _setup_csharp_interface_properties(self, p: dict, properties: dict) -> None:
        """Setup C# interface properties from x-csharp-implements annotation."""
        if self.language == "cs" and "x-csharp-implements" in p:
            p["IMPLEMENTS"] = p["x-csharp-implements"]
            p["INTERFACE_PROPERTIES"] = {}
            if "x-csharp-properties" in p:
                interface_props = p["x-csharp-properties"]
                if isinstance(interface_props, dict):
                    for interface_prop_name, field_name in interface_props.items():
                        if field_name in properties:
                            p["INTERFACE_PROPERTIES"][interface_prop_name] = field_name
        else:
            p["IMPLEMENTS"] = None
            p["INTERFACE_PROPERTIES"] = {}

    def _escape_csharp_property_names(self, p: dict) -> None:
        """Escape C# reserved keywords in property names."""
        for property_name, property_info in p["properties"].items():
            escaped_name = self._escape_csharp_keyword(property_name)
            if escaped_name != property_name:
                property_info["ESCAPED_PROPERTY_NAME"] = escaped_name

        if "constructor_properties" in p:
            for property_name, property_info in p["constructor_properties"].items():
                if "ESCAPED_PROPERTY_NAME" not in property_info:
                    escaped_name = self._escape_csharp_keyword(property_name)
                    if escaped_name != property_name:
                        property_info["ESCAPED_PROPERTY_NAME"] = escaped_name

    def _mark_interface_properties(self, p: dict) -> None:
        """Mark properties that implement C# interface properties."""
        if not p.get("INTERFACE_PROPERTIES"):
            return

        for prop_name, field_name in p["INTERFACE_PROPERTIES"].items():
            if field_name in p["properties"]:
                p["properties"][field_name]["IS_INTERFACE_PROPERTY"] = True
                p["properties"][field_name]["INTERFACE_PROPERTY_NAME"] = prop_name

    def _process_class_properties(self, p: dict, properties: dict, p_base: dict | None = None) -> dict:
        """Process properties for a class, handling inheritance if needed."""
        required_fields = p.get("required", [])
        constructor_properties = {}
        new_properties = {}

        for property, property_info in properties.items():
            if p_base and property in p_base["properties"]:
                if self.config.ignoreSubClassOverrides:
                    continue
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"]["modifier"] = "new "

            is_required = property in required_fields
            TYPE = self._process_property_type(property_info, property, is_required)

            if "type" in TYPE:
                constructor_properties[property] = property_info
                new_properties[property] = property_info

        p["properties"] = new_properties
        return constructor_properties

    def _generate_validation_code(self, class_info: Dict[str, Any], class_name: str) -> list[str]:
        """Generate validation code for all fields in a class"""
        if not self.validator:
            return []

        validations = []
        properties = class_info.get("constructor_properties", {})
        required_fields = class_info.get("required", [])

        for field_name, field_info in properties.items():
            if field_name in self.config.global_ignore_fields:
                continue

            is_required = field_name in required_fields

            # Get the translated type from the processed field info
            field_type = field_info.get("TYPE", {}).get("type", "")

            # Generate validation for this field
            field_validations = self.validator.generate_field_validation(field_name, field_info, field_type, is_required)

            # Check if we need 're' import for pattern validation
            if self.validator.needs_re_import(field_info):
                self.needs_re_import = True

            validations.extend(field_validations)

        return validations

    def _handle_inline_object(self, type_info, field_name, is_required=True):
        """Handle inline object definitions by generating nested classes"""
        # Never treat $ref items as inline objects - they reference $defs
        if "$ref" in type_info:
            raise Exception(f"_handle_inline_object should not be called for $ref items. Field: {field_name}, $ref: {type_info['$ref']}")

        # Generate a unique class name for this inline object based on the field name and parent context
        inline_class_name = self._generate_inline_class_name(field_name)

        # Store the inline object definition for later class generation
        self.class_info[inline_class_name] = type_info

        # Return the class name as the type
        result = {"type": inline_class_name}
        if "default" in type_info:
            result["init"] = self.format_field_with_metadata(type_info["default"], inline_class_name)
        elif not is_required:
            return self.optional_type(inline_class_name)
        return result

    def _generate_inline_class_name(self, field_name):
        """Generate a meaningful class name for an inline object based on the field name and parent context

        NOTE: This should NEVER be called for $ref items - $ref items must use their $def name
        """
        # Use the pre-determined unique name from the analysis phase only if there are collisions
        if hasattr(self, "inline_class_name_mapping") and hasattr(self, "_current_parent_context") and len(self.inline_class_name_mapping) > 0:
            key = (self._current_parent_context, field_name)
            if key in self.inline_class_name_mapping:
                return self.inline_class_name_mapping[key]

        # Fallback to simple PascalCase conversion
        return self._to_pascal_case(field_name)

    def _to_pascal_case(self, text):
        """Convert text to PascalCase"""
        # If the text is already in PascalCase (starts with uppercase and contains no separators),
        # return it as-is to preserve acronyms like DHMessage
        import re

        # Check if text is already in PascalCase format (no separators, starts with uppercase)
        if text and text[0].isupper() and re.match(r"^[a-zA-Z0-9]+$", text):
            result = text
        else:
            # Split on camelCase boundaries and non-alphanumeric characters
            # This handles cases like "buttonObject" -> ["button", "Object"]
            words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text)
            result = "".join(snake_to_pascal_case(word) for word in words)

        # For C#, check if the result is a reserved keyword and rename it
        if self.language == "cs" and result.lower() in self.CS_RESERVED_KEYWORDS:
            result = result + "Type"  # e.g., "object" -> "ObjectType", "string" -> "StringType"

        return result

    def _escape_csharp_keyword(self, name: str) -> str:
        """Escape C# reserved keywords by prefixing with @"""
        if self.language == "cs" and name.lower() in self.CS_RESERVED_KEYWORDS:
            return f"@{name}"
        return name

    def _analyze_name_collisions(self):
        """Phase 1: Analyze schema to detect name collisions and determine unique class names"""
        # Initialize the name mapping dictionary
        self.inline_class_name_mapping = {}

        # Collect all potential inline class names from the schema
        self._collect_inline_class_names(self.schema, self.class_name)

        # Process definitions if they exist
        definitions = self.schema.get("definitions") or self.schema.get("$defs")
        if definitions:
            for class_name, info in definitions.items():
                if isinstance(info, str) or class_name.startswith("_comment"):
                    continue
                self._collect_inline_class_names(info, self._to_pascal_case(class_name))

    def _collect_inline_class_names(self, schema_part, parent_context):
        """Recursively collect inline class names from a schema part"""
        if not isinstance(schema_part, dict):
            return

        # Check if this is an object with properties (potential inline class)
        if "properties" in schema_part:
            for field_name, field_info in schema_part["properties"].items():
                if isinstance(field_info, dict):
                    # NEVER create inline class names for $ref items - they use $def names
                    if "$ref" in field_info:
                        # Skip $ref items - they reference $defs, not inline objects
                        continue
                    if "type" in field_info:
                        if field_info["type"] == "object" and "properties" in field_info:
                            # This is an inline object (not a $ref)
                            base_name = self._to_pascal_case(field_name)
                            unique_name = self._get_unique_class_name(base_name, parent_context)
                            self.inline_class_name_mapping[(parent_context, field_name)] = unique_name

                            # Recursively process nested inline objects
                            self._collect_inline_class_names(field_info, unique_name)
                    elif field_info["type"] == "array" and "items" in field_info:
                        # Check if array items are inline objects
                        items_info = field_info["items"]
                        # Skip if items have a $ref - they reference a $def, not an inline object
                        if isinstance(items_info, dict) and "$ref" not in items_info and "type" in items_info:
                            if items_info["type"] == "object" and "properties" in items_info:
                                # Array of inline objects
                                base_name = self._to_pascal_case(field_name)
                                unique_name = self._get_unique_class_name(base_name, parent_context)
                                self.inline_class_name_mapping[(parent_context, field_name)] = unique_name

                                # Recursively process nested inline objects
                                self._collect_inline_class_names(items_info, unique_name)

    def _get_unique_class_name(self, base_name, parent_context):
        """Get a unique class name, using parent context to ensure uniqueness"""
        # Always use parent context to create unique names for inline objects
        # This ensures that inline objects are properly namespaced
        unique_name = f"{parent_context}{base_name}"
        return unique_name

    def generate(self):
        # Phase 1: Analyze schema to detect name collisions and determine unique class names
        self._analyze_name_collisions()

        # Phase 2: Generate code using pre-determined unique class names
        # Clear class_info to start fresh in Phase 2
        self.class_info = {}

        definitions = self.schema.get("definitions") or self.schema.get("$defs")

        # Default to using definitions order if no explicit order is provided
        if not self.config.order_classes and definitions:
            self.config.order_classes = list(definitions.keys())

        has_top_level_properties = "properties" in self.schema

        # Allow schemas with either definitions OR top-level properties
        if definitions is None and not has_top_level_properties:
            raise Exception("No definitions or top-level properties found in schema")

        # Create mapping from original definition keys to PascalCase class names
        self.definition_name_mapping = {}
        if definitions is not None:
            for k, v in definitions.items():
                # Skip comment fields which are strings, not schema objects
                if isinstance(v, str) or k.startswith("_comment"):
                    continue
                # Skip external $ref definitions (they reference classes in other files)
                if CodeGenerator._is_external_ref(v):
                    continue
                pascal_case_name = self._to_pascal_case(k)
                self.definition_name_mapping[k] = pascal_case_name
                # Store class info with PascalCase name
                self.preprocess(pascal_case_name, v)

        # Prepare top-level class if it has properties
        top_level_class_info = None
        if has_top_level_properties:
            top_level_class_info = self.prepare_class_info(self.class_name, self.schema)

        # Collect class content first to gather all type aliases
        class_content = ""

        def run_class_generator(k, v, prepared_info=None):
            nonlocal class_content
            if k in self.config.ignore_classes:
                return
            p = prepared_info if prepared_info is not None else self.prepare_class_info(k, v)
            if p is None:
                # This was converted to a type alias, skip class generation
                return
            if k == "DHMChatEventFinished":
                print(p)
            try:
                s = self.class_model.render(p)
                # Python needs two blank lines between classes, C# needs none
                if self.language == "python":
                    class_content += s + "\n\n"
                else:
                    class_content += s + "\n"
            except Exception as e:
                print(f"Error generating class {k}: {e}")
                raise e from None

        # Discover nested inline classes by processing existing inline classes
        # This ensures we find all nested inline objects before generating classes
        processed_classes = set()
        while True:
            new_classes_found = False
            for class_name, class_info in list(self.class_info.items()):
                if class_name not in processed_classes and "properties" in class_info:
                    # Set the parent context for this class
                    self._current_parent_context = class_name
                    required_fields = class_info.get("required", [])
                    for property_name, property_info in class_info["properties"].items():
                        if property_name not in self.config.global_ignore_fields:
                            is_property_required = property_name in required_fields
                            self.translate_type(property_info, property_name, is_required=is_property_required)
                    processed_classes.add(class_name)
                    new_classes_found = True
            if not new_classes_found:
                break

        # Generate top-level class first if it exists
        if top_level_class_info is not None:
            run_class_generator(self.class_name, self.schema, top_level_class_info)

        # Generate classes from definitions
        if definitions is not None:
            for k in self.config.order_classes:
                if k in definitions:
                    # Skip external $ref definitions
                    v = definitions[k]
                    if CodeGenerator._is_external_ref(v):
                        continue
                    pascal_case_name = self.definition_name_mapping.get(k, k)
                    if pascal_case_name in self.definition_name_mapping.values():
                        run_class_generator(pascal_case_name, v)

            for k, v in definitions.items():
                # Skip comment fields which are strings, not schema objects
                if isinstance(v, str) or k.startswith("_comment"):
                    continue
                # Skip external $ref definitions
                if CodeGenerator._is_external_ref(v):
                    continue
                if k not in self.config.order_classes:
                    pascal_case_name = self.definition_name_mapping.get(k, k)
                    run_class_generator(pascal_case_name, v)

        # Generate inline classes that were discovered during type processing
        # Get all inline classes (those not in definitions but in class_info)
        # IMPORTANT: Never generate inline classes for $ref items - they should use $def names
        inline_classes = set(self.class_info.keys())
        if definitions is not None:
            # Remove definition classes using their PascalCase names
            # This ensures $def names take priority - if a class exists in definitions,
            # it should be generated from definitions, not as an inline class
            pascal_case_definitions = set(self.definition_name_mapping.values())
            inline_classes -= pascal_case_definitions

            # Also remove any inline classes that match $def names (safety check)
            # This prevents duplicate classes with different names
            for def_key, def_pascal_name in self.definition_name_mapping.items():
                inline_classes.discard(def_pascal_name)

        # Remove the top-level class if it exists
        if top_level_class_info is not None:
            inline_classes.discard(self.class_name)

        for inline_class_name in sorted(inline_classes):
            # Double-check: don't generate if this matches a $def name
            if definitions is not None and inline_class_name in self.definition_name_mapping.values():
                continue
            run_class_generator(inline_class_name, self.class_info[inline_class_name])

        # Separate type aliases into those with forward references and those without
        forward_ref_aliases = []
        simple_aliases = []

        # Get all class names defined in this schema
        defined_classes = set()

        # Add top-level class if it exists
        if top_level_class_info is not None:
            defined_classes.add(self.class_name)

        # Add classes from definitions
        if definitions is not None:
            for k, v in definitions.items():
                if isinstance(v, str) or k.startswith("_comment"):
                    continue
                if k not in self.config.ignore_classes:
                    # Check if this would generate a class (not just a type alias)
                    pascal_case_name = self.definition_name_mapping.get(k, k)
                    test_info = self.prepare_class_info(pascal_case_name, v)
                    if test_info is not None:  # This generates a class
                        defined_classes.add(pascal_case_name)

        # Add inline classes
        inline_classes = set(self.class_info.keys())
        if definitions is not None:
            # Remove definition classes using their PascalCase names
            pascal_case_definitions = set(self.definition_name_mapping.values())
            inline_classes -= pascal_case_definitions
        if top_level_class_info is not None:
            inline_classes.discard(self.class_name)
        defined_classes.update(inline_classes)

        for alias in self.type_aliases:
            # Check if this alias references any of the defined classes
            alias_name, alias_def = alias.split(" = ", 1)
            references_classes = any(class_name in alias_def for class_name in defined_classes)

            if references_classes:
                forward_ref_aliases.append(alias)
            else:
                simple_aliases.append(alias)

        # Sort aliases
        sorted_simple_aliases = sorted(simple_aliases)
        sorted_forward_ref_aliases = sorted(forward_ref_aliases)

        generation_comment = self._generate_command_comment()

        if self.language == "python":
            required_imports = self._assemble_python_imports()
        else:
            required_imports = sorted(list(self.required_imports))

        # Render prefix with only simple aliases (no forward references)
        out = self.prefix.render(
            type_aliases=sorted_simple_aliases,
            generation_comment=generation_comment,
            required_imports=required_imports,
        )
        out += class_content

        # Add forward reference aliases after classes
        if sorted_forward_ref_aliases:
            for alias in sorted_forward_ref_aliases:
                out += alias + "\n"
            out += "\n"

        out += self.suffix.render()

        return out
