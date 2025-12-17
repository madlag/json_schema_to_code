"""
Configuration for the code generator pipeline V3.

Extends the V2 configuration with formatter and output options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OutputMode(str, Enum):
    """Output mode for file generation.

    Controls behavior when the output file already exists.
    """

    ERROR_IF_EXISTS = "error"  # Default: raise error if file exists
    FORCE = "force"  # Overwrite without merging
    MERGE = "merge"  # Merge with existing file, preserving custom code


@dataclass
class OutputConfig:
    """Configuration for output file handling.

    Attributes:
        mode: How to handle existing output files
        validate_before_write: Whether to validate code before writing
        atomic_write: Whether to use atomic file writes
    """

    mode: OutputMode = OutputMode.ERROR_IF_EXISTS
    validate_before_write: bool = True
    atomic_write: bool = True


@dataclass
class FormatterConfig:
    """Configuration for post-processing formatters."""

    # Whether formatting is enabled
    enabled: bool = False

    # Line length for the formatter
    line_length: int = 100

    # Python version target (e.g., "py312", "py313")
    target_version: str = "py312"

    # Whether to use string normalization (convert single quotes to double)
    string_normalization: bool = True

    # Whether to format docstrings
    magic_trailing_comma: bool = True


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
    csharp_namespace: str = ""  # Namespace to wrap all types in (e.g., "MyApp.Models")
    csharp_additional_usings: list[str] = field(default_factory=list)  # Extra using statements

    # Formatter configuration (V3 addition)
    formatter: FormatterConfig = field(default_factory=FormatterConfig)

    # Output configuration (V3 addition)
    output: OutputConfig = field(default_factory=OutputConfig)

    @staticmethod
    def from_dict(d: dict) -> CodeGeneratorConfig:
        """Create a config from a dictionary."""
        config = CodeGeneratorConfig()
        for k, v in d.items():
            if k == "formatter" and isinstance(v, dict):
                config.formatter = FormatterConfig(**v)
            elif k == "output" and isinstance(v, dict):
                mode = v.get("mode", OutputMode.ERROR_IF_EXISTS)
                if isinstance(mode, str):
                    mode = OutputMode(mode)
                config.output = OutputConfig(
                    mode=mode,
                    validate_before_write=v.get("validate_before_write", True),
                    atomic_write=v.get("atomic_write", True),
                )
            elif hasattr(config, k):
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
            "csharp_namespace": self.csharp_namespace,
            "csharp_additional_usings": self.csharp_additional_usings,
            "formatter": {
                "enabled": self.formatter.enabled,
                "line_length": self.formatter.line_length,
                "target_version": self.formatter.target_version,
                "string_normalization": self.formatter.string_normalization,
                "magic_trailing_comma": self.formatter.magic_trailing_comma,
            },
            "output": {
                "mode": self.output.mode.value,
                "validate_before_write": self.output.validate_before_write,
                "atomic_write": self.output.atomic_write,
            },
        }
