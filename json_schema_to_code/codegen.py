import collections
import copy
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import jinja2

from . import __version__
from .cli_utils import reconstruct_command_line

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

    @staticmethod
    def from_dict(d):
        config = CodeGeneratorConfig()
        for k, v in d.items():
            setattr(config, k, v)
        return config


class CodeGenerator:
    # Language-specific import mappings
    # None means the feature exists but requires no import
    PYTHON_IMPORT_MAP = {
        ImportType.LIST: None,
        ImportType.TUPLE: None,
        ImportType.BASE: [
            ("dataclasses", "dataclass"),
            ("dataclasses", "field"),
            ("dataclasses_json", "dataclass_json"),
            ("dataclasses_json", "config"),
        ],
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

    def __init__(
        self, class_name: str, schema: Dict[str, Any], config: CodeGeneratorConfig, language: str
    ):
        self.class_name = class_name
        self.schema = schema
        self.config = config
        self.language = language
        self.jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)
        language_to_extension = {"cs": "cs", "python": "py"}
        extension = language_to_extension[language]
        self.prefix = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/prefix.{extension}.jinja2").read()
        )
        self.class_model = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/class.{extension}.jinja2").read()
        )
        self.suffix = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/suffix.{extension}.jinja2").read()
        )

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

    def _create_default_factory_value(
        self, container_type: str, default_value, type_name: str | None = None
    ) -> str:
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
                    return "field(default_factory=list, metadata=config(exclude=lambda x: len(x) == 0))"
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
                        return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
                else:  # C# and other languages
                    content = ", ".join(formatted_items)
                return patterns["populated_list"].format(content=content, type_name=type_name)

        elif container_type == "dict":
            if is_empty:
                base_pattern = patterns["empty_dict"].format(type_name=type_name)
                if self.config.exclude_default_value_from_json and self.language == "python":
                    return "field(default_factory=dict, metadata=config(exclude=lambda x: len(x) == 0))"
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
                        return f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))"
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

        # Assemble import statements - __future__ imports must come first
        assembled_imports = []

        # Handle __future__ imports first (they must be at the top)
        if "__future__" in import_groups:
            names = sorted(import_groups["__future__"])
            if len(names) == 1:
                assembled_imports.append(f"from __future__ import {names[0]}")
            else:
                assembled_imports.append(f"from __future__ import {', '.join(names)}")
            del import_groups["__future__"]

        # Handle other imports in sorted order
        for module in sorted(import_groups.keys()):
            names = sorted(import_groups[module])
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
        comment_prefix = "//" if self.language == "cs" else "#"

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
                    unquoted_types = [
                        t.strip('"') if t.startswith('"') and t.endswith('"') else t
                        for t in sorted_types
                    ]
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
                    unquoted_for_alias = [
                        t.strip('"') if t.startswith('"') and t.endswith('"') else t
                        for t in sorted_types
                    ]
                    capitalized_types = [t.capitalize() for t in unquoted_for_alias]
                    type_alias_name = "Or".join(capitalized_types)

                    # Generate the type alias definition
                    type_alias_def = f"{type_alias_name} = {quoted_union}"
                    self.type_aliases.add(type_alias_def)

                    return type_alias_name
            case "cs":
                if self.config.use_inline_unions:
                    # C# doesn't support inline unions, use object as fallback
                    raise Exception("Fix Union type for cs")
                else:
                    # Generate type alias for C# (even though it's still object, keep the naming)
                    capitalized_types = [t.capitalize() for t in sorted_types]
                    type_alias_name = "Or".join(capitalized_types)

                    # For C#, type aliases still resolve to object but keep the naming
                    type_alias_def = f"// {type_alias_name} = object (union type)"
                    self.type_aliases.add(type_alias_def)

                    return type_alias_name
            case _:
                raise Exception("Fix Union type for " + self.language)

    def const_type(self, t: Dict[str, Any]) -> Dict[str, Any]:
        match self.language:
            case "python":
                const = t["const"]
                self.register_import_needed(ImportType.LITERAL)
                return {"type": f'Literal["{const}"]', "init": f'"{const}"'}
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

    def ref_type(self, ref: str) -> str:
        type_name = ref.split("/")[-1]

        # For Python, quote types that are in the quoted_types_for_python list
        type_name = self.quote_type(type_name)

        return type_name

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

    def _handle_union_type_with_defaults(
        self, type_info, union_key: str, field_name: str, is_required: bool
    ) -> dict:
        """Helper method to handle oneOf/anyOf types with proper default value handling"""
        types = [
            self.translate_type(t, f"{field_name}_union", is_required=True)["type"]
            for t in type_info[union_key]
        ]
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
            return f'"{escaped_value}"'

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
        return f"field(default={formatted_default}, metadata=config(exclude=lambda x: {exclude_condition}))"

    def translate_type(self, type_info, field_name, is_required=True):
        """
        Translate type information from JSON schema to target language type.

        Args:
            type_info: JSON schema type information
            field_name: Name of the field being processed (used for inline object naming)
            is_required: Whether this property is required (affects nullability)
        """
        if "type" in type_info:
            type = type_info["type"]
            list_type = self.type_map["list"]
            tuple_type = self.type_map["tuple"]
            if type == "array":
                if isinstance(type_info["items"], dict):
                    item_type_info = self.translate_type(
                        type_info["items"], field_name, is_required=True
                    )  # Array items are always considered required
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

                    if (
                        type_info.get("minItems") != type_info.get("maxItems")
                        or not self.config.use_tuples
                    ):
                        if not self.config.use_array_of_super_type_for_variable_length_tuple:
                            # Check if all items are of the same type
                            item_types = [
                                self.translate_type(t, field_name, is_required=True)["type"]
                                for t in type_info["items"]
                            ]

                            for item_type in item_types[1:]:
                                # Items are not of the same type
                                if item_type != item_types[0]:
                                    raise Exception(
                                        "The items are not of the same type: " + str(item_types)
                                    )
                        item_type = self.super_type(type_info["items"])
                        item_type = self.translate_type(item_type, field_name, is_required=True)
                        self.register_import_needed(ImportType.LIST)
                        type = f"{list_type}{self.type_brackets[0]}{item_type['type']}{self.type_brackets[1]}"
                    elif self.config.use_tuples:
                        item_types = [
                            self.translate_type(t, field_name, is_required=True)["type"]
                            for t in type_info["items"]
                        ]
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
                    base_type = self.translate_type(
                        {"type": type[0]}, f"{field_name}_union", is_required=True
                    )["type"]
                    if nullable:
                        result = self.optional_type(base_type)
                        # Handle default values for nullable types
                        if "default" in type_info:
                            result["init"] = self.format_field_with_metadata(
                                type_info["default"], result["type"]
                            )
                        return result
                    else:
                        result = {"type": base_type}
                        if "default" in type_info:
                            result["init"] = self.format_field_with_metadata(
                                type_info["default"], base_type
                            )
                        elif not is_required:
                            # Property is not required and has no default - make it nullable
                            return self.optional_type(base_type)
                        return result
                else:
                    # Use union_type for consistent logic
                    typeNames = [
                        self.translate_type({"type": t}, f"{field_name}_union", is_required=True)[
                            "type"
                        ]
                        for t in type
                    ]
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
        elif "$ref" in type_info:
            type = self.ref_type(type_info["$ref"])
        elif "const" in type_info:
            return self.const_type(type_info)
        elif "enum" in type_info:
            # TODO deduplicate code handling enums here and lower
            class_name = None
            for e in type_info["enum"]:
                c = e.__class__.__name__
                if class_name is None or c == class_name:
                    class_name = c
                else:
                    raise Exception("Enums with different types are not supported")
            mapping = {"str": "string", "int": "integer", "float": "float"}
            class_name = mapping.get(class_name, class_name)  # type: ignore
            Warning(
                f"We should have information about what values are allowed for enum {class_name}"
            )
            comment = "// Allowed values: " + ", ".join([f'"{e}"' for e in type_info["enum"]])
            return {"type": self.type_map[class_name], "comment": comment}
        elif "oneOf" in type_info or "anyOf" in type_info:
            union_key = "oneOf" if "oneOf" in type_info else "anyOf"
            return self._handle_union_type_with_defaults(
                type_info, union_key, field_name, is_required
            )
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

    def preprocess(self, class_name, info):
        p = copy.deepcopy(info)
        if "allOf" in p:
            allOf = p["allOf"]
            base_class = self.ref_type(allOf[0]["$ref"])
            # Change class_name camelcase to snake_case
            json_name = self.convert_message_class_to_json_name(
                allOf[1].get("properties", {}), class_name
            )
            if class_name not in self.config.ignore_classes:
                self.subclasses[base_class].append([class_name, json_name])
            self.base_class[class_name] = base_class
        self.class_info[class_name] = p

    def prepare_class_info(self, class_name, info):
        """Wrapper function that catches exceptions and adds class name context"""
        try:
            return self._prepare_class_info(class_name, info)
        except Exception as e:
            raise Exception(f"Error processing class '{class_name}': {str(e)}") from e

    def _prepare_class_info(self, class_name, info):
        p = copy.deepcopy(info)

        if "allOf" in p:
            extends = self.ref_type(p["allOf"][0]["$ref"])
            p = p["allOf"][1]
            p["EXTENDS"] = extends

        # Check if this is a oneOf with multiple $ref - create type alias instead of class
        if "oneOf" in p and all("$ref" in item for item in p["oneOf"]) and len(p["oneOf"]) > 1:
            # This should be a type alias, not a class - skip class generation
            union_types = [self.ref_type(item["$ref"]) for item in p["oneOf"]]

            if self.config.use_inline_unions:
                # Create explicit type alias even with inline unions enabled
                union_string = " | ".join(sorted(union_types))
                # Handle quoted types properly
                has_quoted_types = any(t.startswith('"') and t.endswith('"') for t in union_types)
                if has_quoted_types:
                    unquoted_types = [
                        t.strip('"') if t.startswith('"') and t.endswith('"') else t
                        for t in union_types
                    ]
                    union_string = " | ".join(sorted(unquoted_types))
                    union_string = f'"{union_string}"'

                type_alias_def = f"{class_name} = {union_string}"
                self.type_aliases.add(type_alias_def)
            else:
                # Use the existing union_type method which will create the alias
                union_type_name = self.union_type(union_types)
                # Override the generated name with our class name
                old_alias = None
                for alias in self.type_aliases:
                    if alias.startswith(union_type_name + " ="):
                        old_alias = alias
                        break
                if old_alias:
                    self.type_aliases.remove(old_alias)
                    # Create new alias with the class name
                    union_string = old_alias.split(" = ", 1)[1]
                    type_alias_def = f"{class_name} = {union_string}"
                    self.type_aliases.add(type_alias_def)

            # Mark this as a type alias so it won't generate a class
            return None

        if ("anyOf" in p or "oneOf" in p) or ("type" in p and p["type"] != "object"):
            # Handle anyOf/oneOf at class level or non-object types - treat as union/base type
            base_type = self.translate_type(p, f"{class_name}_base", is_required=True)["type"]
            p["EXTENDS"] = base_type
            self.base_class[class_name] = base_type
            if base_type not in self.class_info:
                self.class_info[base_type] = {"properties": {}}

        p["CLASS_NAME"] = class_name
        p["SUB_CLASSES"] = self.subclasses.get(class_name, [])

        # Track imports
        if p["SUB_CLASSES"]:
            self.register_import_needed(ImportType.SUB_CLASSES)
        if "enum" in p and p["enum"]:
            self.register_import_needed(ImportType.ENUM)

        properties = p.get("properties", {})

        if p.get("EXTENDS") is not None:
            p["BASE_PROPERTIES"] = dict()

            bc = self.base_class[class_name]
            if bc not in self.class_info:
                raise Exception(f"Base class {bc} not found for class {class_name}")
            p_base = self.class_info.get(bc)
            constructor_properties = dict()
            for property, property_info in p_base["properties"].items():  # type: ignore
                # For base class properties, we need to check if they're required in the base class
                base_required = p_base.get("required", [])  # type: ignore
                is_property_required = property in base_required
                TYPE = self.translate_type(
                    property_info, property, is_required=is_property_required
                )
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"].update(TYPE)
                child_property_info = p.get("properties", {}).get(property)
                if child_property_info is not None and "const" in child_property_info:
                    const = '"' + child_property_info["const"] + '"'
                    p["BASE_PROPERTIES"][const] = property_info
                else:
                    constructor_properties[property] = property_info
                    p["BASE_PROPERTIES"][property] = property_info

            new_properties = dict()
            required_fields = p.get("required", [])
            for property, property_info in properties.items():
                override_base_property = property in p_base["properties"]  # type: ignore
                if override_base_property and self.config.ignoreSubClassOverrides:
                    continue

                is_property_required = property in required_fields
                TYPE = self.translate_type(
                    property_info, property, is_required=is_property_required
                )
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"].update(TYPE)
                type_modifier = "new " if override_base_property else ""
                property_info["TYPE"]["modifier"] = type_modifier

                if "type" in TYPE:
                    constructor_properties[property] = property_info
                    new_properties[property] = property_info

            p["properties"] = new_properties
            p["constructor_properties"] = constructor_properties
        else:
            p["constructor_properties"] = properties
            required_fields = p.get("required", [])

            for property, property_info in properties.items():
                is_property_required = property in required_fields
                TYPE = self.translate_type(
                    property_info, property, is_required=is_property_required
                )
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"].update(TYPE)

        if "enum" in p:
            p["enum"] = {k.upper(): k for k in p["enum"]}
        else:
            p["enum"] = {}

        if "properties" in p:
            p["properties"] = {
                k: v
                for k, v in p["properties"].items()
                if k not in self.config.global_ignore_fields
            }
        else:
            p["properties"] = {}
        if "constructor_properties" in p:
            p["constructor_properties"] = {
                k: v
                for k, v in p["constructor_properties"].items()
                if k not in self.config.global_ignore_fields
            }

        return p

    def _handle_inline_object(self, type_info, field_name, is_required=True):
        """Handle inline object definitions by generating nested classes"""
        # Generate a unique class name for this inline object based on the field name
        inline_class_name = self._generate_inline_class_name(field_name)

        # Store the inline object definition for later class generation
        self.class_info[inline_class_name] = type_info

        # Return the class name as the type
        result = {"type": inline_class_name}
        if "default" in type_info:
            result["init"] = self.format_field_with_metadata(
                type_info["default"], inline_class_name
            )
        elif not is_required:
            return self.optional_type(inline_class_name)
        return result

    def _generate_inline_class_name(self, field_name):
        """Generate a meaningful class name for an inline object based on the field name"""
        return self._to_pascal_case(field_name)

    def _to_pascal_case(self, text):
        """Convert text to PascalCase"""
        # Remove non-alphanumeric characters and split
        import re

        words = re.findall(r"[a-zA-Z0-9]+", text)
        return "".join(word.capitalize() for word in words)

    def generate(self):
        definitions = self.schema.get("definitions") or self.schema.get("$defs")
        has_top_level_properties = "properties" in self.schema

        # Allow schemas with either definitions OR top-level properties
        if definitions is None and not has_top_level_properties:
            raise Exception("No definitions or top-level properties found in schema")

        # Process definitions if they exist
        if definitions is not None:
            for k, v in definitions.items():
                # Skip comment fields which are strings, not schema objects
                if isinstance(v, str) or k.startswith("_comment"):
                    continue
                self.preprocess(k, v)

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
                    required_fields = class_info.get("required", [])
                    for property_name, property_info in class_info["properties"].items():
                        if property_name not in self.config.global_ignore_fields:
                            is_property_required = property_name in required_fields
                            self.translate_type(
                                property_info, property_name, is_required=is_property_required
                            )
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
                    run_class_generator(k, definitions[k])

            for k, v in definitions.items():
                # Skip comment fields which are strings, not schema objects
                if isinstance(v, str) or k.startswith("_comment"):
                    continue
                if k not in self.config.order_classes:
                    run_class_generator(k, v)

        # Generate inline classes that were discovered during type processing
        # Get all inline classes (those not in definitions but in class_info)
        inline_classes = set(self.class_info.keys())
        if definitions is not None:
            inline_classes -= set(definitions.keys())
        # Remove the top-level class if it exists
        if top_level_class_info is not None:
            inline_classes.discard(self.class_name)

        for inline_class_name in sorted(inline_classes):
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
                    test_info = self.prepare_class_info(k, v)
                    if test_info is not None:  # This generates a class
                        defined_classes.add(k)

        # Add inline classes
        inline_classes = set(self.class_info.keys())
        if definitions is not None:
            inline_classes -= set(definitions.keys())
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
