"""
Validation code generator for JSON schema constraints.

This module generates runtime validation code based on JSON schema constraints
for both Python and C# targets using validation rule objects.
"""

import re
from typing import Any, Dict, List

from .validation_rules import (
    ArrayItemTypeRule,
    ConstRule,
    EnumRule,
    ExclusiveMaximumRule,
    ExclusiveMinimumRule,
    MaximumRule,
    MaxItemsRule,
    MaxLengthRule,
    MinimumRule,
    MinItemsRule,
    MinLengthRule,
    MultipleOfRule,
    NonEmptyStringRule,
    PatternRule,
    ReferenceTypeCheckRule,
    TypeCheckRule,
    ValidationRule,
)


class ValidationGenerator:
    """Generate validation code from JSON schema constraints using rule objects"""

    def __init__(self, language: str):
        """
        Initialize the validation generator.

        Args:
            language: Target language ('python' or 'cs')
        """
        self.language = language

    def generate_field_validation(
        self,
        field_name: str,
        field_info: Dict[str, Any],
        field_type: str,
        is_required: bool,
    ) -> List[str]:
        """
        Generate validation code for a single field.

        Args:
            field_name: Name of the field to validate
            field_info: JSON schema information for the field
            field_type: The translated type of the field
            is_required: Whether the field is required

        Returns:
            List of validation code lines
        """
        rules: List[ValidationRule] = []

        if self.language == "python":
            rules = self._create_python_rules(field_name, field_info, field_type, is_required)
        elif self.language == "cs":
            rules = self._create_cs_rules(field_name, field_info, field_type, is_required)

        # Generate code from all rules
        code_lines = []
        for rule in rules:
            code_lines.extend(rule.generate_code())

        return code_lines

    def _create_python_rules(
        self,
        field_name: str,
        field_info: Dict[str, Any],
        field_type: str,
        is_required: bool,
    ) -> List[ValidationRule]:
        """Create validation rules for Python"""
        rules = []

        # Handle $ref types - validate type
        if "$ref" in field_info:
            ref_type = field_info["$ref"].split("/")[-1]
            class_name = self._to_pascal_case(ref_type)
            rules.append(ReferenceTypeCheckRule(field_name, self.language, class_name))
            return rules

        base_type = field_info.get("type")

        # Handle array types
        if base_type == "array":
            rules.extend(self._create_array_rules(field_name, field_info, is_required))

        # Handle string types
        elif base_type == "string":
            rules.extend(self._create_string_rules(field_name, field_info, is_required))

        # Handle numeric types
        elif base_type in ["integer", "number"]:
            rules.extend(self._create_numeric_rules(field_name, field_info, is_required))

        # Handle boolean types
        elif base_type == "boolean":
            if is_required:
                rules.append(TypeCheckRule(field_name, self.language, "bool"))

        # Handle object types (but not inline objects with properties)
        elif base_type == "object" and "properties" not in field_info:
            if is_required:
                rules.append(TypeCheckRule(field_name, self.language, "dict"))

        # Handle enum types
        if "enum" in field_info:
            rules.append(EnumRule(field_name, self.language, field_info["enum"]))

        # Handle const types
        if "const" in field_info:
            rules.append(ConstRule(field_name, self.language, field_info["const"]))

        return rules

    def _create_cs_rules(
        self,
        field_name: str,
        field_info: Dict[str, Any],
        field_type: str,
        is_required: bool,
    ) -> List[ValidationRule]:
        """Create validation rules for C#"""
        rules = []

        # Handle $ref types
        if "$ref" in field_info:
            if is_required:
                ref_type = field_info["$ref"].split("/")[-1]
                class_name = self._to_pascal_case(ref_type)
                rules.append(ReferenceTypeCheckRule(field_name, self.language, class_name))
            return rules

        base_type = field_info.get("type")

        # Handle array types
        if base_type == "array":
            rules.extend(self._create_array_rules(field_name, field_info, is_required))

        # Handle string types
        elif base_type == "string":
            rules.extend(self._create_string_rules(field_name, field_info, is_required))

        # Handle numeric types
        elif base_type in ["integer", "number"]:
            rules.extend(self._create_numeric_rules(field_name, field_info, is_required))

        # Handle enum types
        if "enum" in field_info:
            rules.append(EnumRule(field_name, self.language, field_info["enum"]))

        # Handle const types
        if "const" in field_info:
            rules.append(ConstRule(field_name, self.language, field_info["const"]))

        return rules

    def _create_string_rules(
        self, field_name: str, field_info: Dict[str, Any], is_required: bool
    ) -> List[ValidationRule]:
        """Create string validation rules"""
        rules = []

        # Type check and non-empty check
        if is_required:
            rules.append(TypeCheckRule(field_name, self.language, "str"))
            rules.append(NonEmptyStringRule(field_name, self.language))

        # Pattern validation
        if "pattern" in field_info:
            rules.append(PatternRule(field_name, self.language, field_info["pattern"], is_required))

        # Min/max length
        if "minLength" in field_info:
            rules.append(MinLengthRule(field_name, self.language, field_info["minLength"]))

        if "maxLength" in field_info:
            rules.append(MaxLengthRule(field_name, self.language, field_info["maxLength"]))

        return rules

    def _create_numeric_rules(
        self, field_name: str, field_info: Dict[str, Any], is_required: bool
    ) -> List[ValidationRule]:
        """Create numeric validation rules"""
        rules = []

        # Type check
        if is_required:
            num_type = "int" if field_info["type"] == "integer" else "(int, float)"
            rules.append(TypeCheckRule(field_name, self.language, num_type))

        # Minimum value
        if "minimum" in field_info:
            rules.append(MinimumRule(field_name, self.language, field_info["minimum"], is_required))

        if "exclusiveMinimum" in field_info:
            rules.append(
                ExclusiveMinimumRule(
                    field_name, self.language, field_info["exclusiveMinimum"], is_required
                )
            )

        # Maximum value
        if "maximum" in field_info:
            rules.append(MaximumRule(field_name, self.language, field_info["maximum"], is_required))

        if "exclusiveMaximum" in field_info:
            rules.append(
                ExclusiveMaximumRule(
                    field_name, self.language, field_info["exclusiveMaximum"], is_required
                )
            )

        # Multiple of
        if "multipleOf" in field_info:
            rules.append(
                MultipleOfRule(field_name, self.language, field_info["multipleOf"], is_required)
            )

        return rules

    def _create_array_rules(
        self, field_name: str, field_info: Dict[str, Any], is_required: bool
    ) -> List[ValidationRule]:
        """Create array validation rules"""
        rules = []

        # Type check
        if is_required:
            rules.append(TypeCheckRule(field_name, self.language, "list"))

        # Min items
        if "minItems" in field_info:
            rules.append(
                MinItemsRule(field_name, self.language, field_info["minItems"], is_required)
            )

        # Max items
        if "maxItems" in field_info:
            rules.append(
                MaxItemsRule(field_name, self.language, field_info["maxItems"], is_required)
            )

        # Validate array item types if we have a $ref
        if "items" in field_info and isinstance(field_info["items"], dict):
            if "$ref" in field_info["items"]:
                ref_type = field_info["items"]["$ref"].split("/")[-1]
                class_name = self._to_pascal_case(ref_type)
                rules.append(ArrayItemTypeRule(field_name, self.language, class_name))

        return rules

    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase"""
        if text and text[0].isupper() and re.match(r"^[a-zA-Z0-9]+$", text):
            return text
        words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text)
        return "".join(word.capitalize() for word in words)

    def needs_re_import(self, field_info: Dict[str, Any]) -> bool:
        """Check if this field validation requires the 're' module (Python only)"""
        if self.language != "python":
            return False
        return "pattern" in field_info
