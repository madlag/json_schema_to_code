"""
Configuration for the code generator pipeline.

Reuses the same configuration structure as the original codegen.py
for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
