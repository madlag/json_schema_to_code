"""
Configuration for the code generator pipeline.

Reuses the same configuration structure as the original codegen.py
for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OutputMode(str, Enum):
    """Output mode for code generation."""

    ERROR_IF_EXISTS = "error_if_exists"  # Error if output file exists
    FORCE = "force"  # Overwrite existing file
    MERGE = "merge"  # Merge with existing file


class MergeStrategy(str, Enum):
    """Strategy for handling existing value members not present in generated code."""

    ERROR = "error"  # Raise error (default)
    MERGE = "merge"  # Keep extra members from existing file
    DELETE = "delete"  # Remove extra members from existing file


@dataclass
class FormatterConfig:
    """Configuration for code formatters."""

    enabled: bool = True
    line_length: int = 100
    target_version: str = ""  # Python target version (e.g., "py313")
    string_normalization: bool = True  # Normalize strings to double quotes
    magic_trailing_comma: bool = True  # Add trailing comma to multi-line structures


@dataclass
class OutputConfig:
    """Configuration for output handling."""

    mode: OutputMode = OutputMode.MERGE
    merge_strategy: MergeStrategy = MergeStrategy.ERROR
    output_path: str = ""
    validate_before_write: bool = True  # Validate generated code before writing


@dataclass
class CodeGeneratorConfig:
    """Configuration options for code generation."""

    # Classes to ignore during generation
    ignore_classes: list[str] = field(default_factory=list)

    # Fields to ignore globally across all classes
    global_ignore_fields: list[str] = field(default_factory=list)

    # Order in which to generate classes (empty = definition order)
    order_classes: list[str] = field(default_factory=list)

    # Whether to ignore subclass overrides
    ignoreSubClassOverrides: bool = False

    # Whether to drop minItems/maxItems validation
    drop_min_max_items: bool = False

    # Use array of super type for variable length tuples
    use_array_of_super_type_for_variable_length_tuple: bool = True

    # Whether to use tuple types
    use_tuples: bool = True

    # Use inline union syntax instead of type aliases
    use_inline_unions: bool = False

    # Add generation comment at top of file
    add_generation_comment: bool = True

    # Types to quote for Python (forward references)
    quoted_types_for_python: list[str] = field(default_factory=list)

    # Use from __future__ import annotations
    use_future_annotations: bool = True

    # Exclude default values from JSON serialization
    exclude_default_value_from_json: bool = False

    # Add runtime validation code
    add_validation: bool = False

    # External reference import configuration for Python
    external_ref_base_module: str = ""
    external_ref_schema_to_module: dict[str, str] = field(default_factory=dict)

    # C# specific configuration
    csharp_namespace: str = ""
    csharp_additional_usings: list[str] = field(default_factory=list)

    # Base path for resolving external schema $refs
    # When set, the resolver will automatically load external schemas from disk
    # The $ref path is resolved relative to this base path
    # e.g., if base_path="/path/to/schemas" and $ref="/activities/quiz_schema#/$defs/Quiz"
    # it will load "/path/to/schemas/activities/quiz_schema.jinja.json"
    schema_base_path: str = ""

    # Output configuration
    output: OutputConfig = field(default_factory=OutputConfig)

    # Formatter configuration
    formatter: FormatterConfig = field(default_factory=FormatterConfig)

    @staticmethod
    def from_dict(d: dict) -> CodeGeneratorConfig:
        """Create a config from a dictionary."""
        config = CodeGeneratorConfig()
        for k, v in d.items():
            if hasattr(config, k):
                setattr(config, k, v)
        return config

    def to_dict(self) -> dict:
        """Convert config to a dictionary."""
        return {
            "ignore_classes": self.ignore_classes,
            "global_ignore_fields": self.global_ignore_fields,
            "order_classes": self.order_classes,
            "ignoreSubClassOverrides": self.ignoreSubClassOverrides,
            "drop_min_max_items": self.drop_min_max_items,
            "use_array_of_super_type_for_variable_length_tuple": (self.use_array_of_super_type_for_variable_length_tuple),
            "use_tuples": self.use_tuples,
            "use_inline_unions": self.use_inline_unions,
            "add_generation_comment": self.add_generation_comment,
            "quoted_types_for_python": self.quoted_types_for_python,
            "use_future_annotations": self.use_future_annotations,
            "exclude_default_value_from_json": self.exclude_default_value_from_json,
            "add_validation": self.add_validation,
            "external_ref_base_module": self.external_ref_base_module,
            "external_ref_schema_to_module": self.external_ref_schema_to_module,
        }
