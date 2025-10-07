"""
Validation rule objects that generate validation code.

Each rule represents a specific validation constraint from JSON schema
and knows how to generate code for different target languages.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, List


class ValidationRule(ABC):
    """Base class for all validation rules"""

    def __init__(self, field_name: str, language: str, is_required: bool = True):
        """
        Initialize a validation rule.

        Args:
            field_name: Name of the field being validated
            language: Target language ('python' or 'cs')
            is_required: Whether the field is required (affects None checking)
        """
        self.field_name = field_name
        self.language = language
        self.is_required = is_required

    @abstractmethod
    def generate_code(self) -> List[str]:
        """Generate validation code lines for this rule"""
        pass

    def _wrap_with_none_check(self, condition: str) -> str:
        """
        Wrap a condition with a None check for optional fields.

        For Python, this converts "condition" to "field is not None and condition"
        For C#, None checks are typically done separately so this returns as-is.

        Args:
            condition: The condition to wrap

        Returns:
            The condition, optionally wrapped with a None check
        """
        if self.language == "python" and not self.is_required:
            return f"self.{self.field_name} is not None and {condition}"
        return condition

    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase"""
        if text and text[0].isupper() and re.match(r"^[a-zA-Z0-9]+$", text):
            return text
        words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text)
        return "".join(word.capitalize() for word in words)


class TypeCheckRule(ValidationRule):
    """Validates that a field has the correct type"""

    def __init__(self, field_name: str, language: str, expected_type: str):
        super().__init__(field_name, language)
        self.expected_type = expected_type

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if not isinstance(self.{self.field_name}, {self.expected_type}):",
                f'    raise ValueError(f"{self.field_name} must be a {self.expected_type}, got {{type(self.{self.field_name}).__name__}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} == null)",
                f'    throw new ArgumentNullException(nameof({prop_name}), "{prop_name} is required");',
            ]
        return []


class ReferenceTypeCheckRule(ValidationRule):
    """Validates that a field is an instance of a referenced class"""

    def __init__(self, field_name: str, language: str, class_name: str):
        super().__init__(field_name, language)
        self.class_name = class_name

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if not isinstance(self.{self.field_name}, {self.class_name}):",
                f'    raise ValueError(f"{self.field_name} must be a {self.class_name} instance, got {{type(self.{self.field_name}).__name__}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} == null)",
                f'    throw new ArgumentNullException(nameof({prop_name}), "{prop_name} is required");',
            ]
        return []


class NonEmptyStringRule(ValidationRule):
    """Validates that a required string is not empty"""

    def __init__(self, field_name: str, language: str):
        super().__init__(field_name, language)

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if not self.{self.field_name}:",
                f'    raise ValueError("{self.field_name} field is required and cannot be empty")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if (string.IsNullOrEmpty({prop_name}))",
                f'    throw new ArgumentException("{prop_name} is required and cannot be empty", nameof({prop_name}));',
            ]
        return []


class PatternRule(ValidationRule):
    """Validates that a string matches a regex pattern"""

    def __init__(self, field_name: str, language: str, pattern: str, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.pattern = pattern

    def generate_code(self) -> List[str]:
        if self.language == "python":
            # For raw strings (r"..."), we only need to escape quotes, not backslashes
            escaped_pattern = self.pattern.replace('"', '\\"')
            condition = f'not re.match(r"{escaped_pattern}", self.{self.field_name})'
            condition = self._wrap_with_none_check(condition)
            # Use raw f-string for error message to avoid escape sequence warnings
            # Escape quotes and curly braces (f-string syntax requires {{ and }})
            error_pattern = self.pattern.replace('"', '\\"').replace("{", "{{").replace("}", "}}")
            return [
                f"if {condition}:",
                f"    raise ValueError(rf\"{self.field_name} must match pattern '{error_pattern}', got {{self.{self.field_name}!r}}\")",
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            escaped_pattern = self.pattern.replace('"', '\\"')
            return [
                f'if (!System.Text.RegularExpressions.Regex.IsMatch({prop_name}, @"{escaped_pattern}"))',
                f"    throw new ArgumentException($\"{prop_name} must match pattern '{self.pattern}'\", nameof({prop_name}));",
            ]
        return []


class MinLengthRule(ValidationRule):
    """Validates minimum string length"""

    def __init__(self, field_name: str, language: str, min_length: int):
        super().__init__(field_name, language)
        self.min_length = min_length

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if len(self.{self.field_name}) < {self.min_length}:",
                f'    raise ValueError(f"{self.field_name} must be at least {self.min_length} characters, got {{len(self.{self.field_name})}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name}.Length < {self.min_length})",
                f'    throw new ArgumentException($"{prop_name} must be at least {self.min_length} characters", nameof({prop_name}));',
            ]
        return []


class MaxLengthRule(ValidationRule):
    """Validates maximum string length"""

    def __init__(self, field_name: str, language: str, max_length: int):
        super().__init__(field_name, language)
        self.max_length = max_length

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if len(self.{self.field_name}) > {self.max_length}:",
                f'    raise ValueError(f"{self.field_name} must be at most {self.max_length} characters, got {{len(self.{self.field_name})}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name}.Length > {self.max_length})",
                f'    throw new ArgumentException($"{prop_name} must be at most {self.max_length} characters", nameof({prop_name}));',
            ]
        return []


class MinimumRule(ValidationRule):
    """Validates minimum numeric value"""

    def __init__(self, field_name: str, language: str, minimum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.minimum = minimum

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"self.{self.field_name} < {self.minimum}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must be >= {self.minimum}, got {{self.{self.field_name}}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} < {self.minimum})",
                f'    throw new ArgumentException($"{prop_name} must be >= {self.minimum}", nameof({prop_name}));',
            ]
        return []


class MaximumRule(ValidationRule):
    """Validates maximum numeric value"""

    def __init__(self, field_name: str, language: str, maximum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.maximum = maximum

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"self.{self.field_name} > {self.maximum}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must be <= {self.maximum}, got {{self.{self.field_name}}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} > {self.maximum})",
                f'    throw new ArgumentException($"{prop_name} must be <= {self.maximum}", nameof({prop_name}));',
            ]
        return []


class ExclusiveMinimumRule(ValidationRule):
    """Validates exclusive minimum numeric value"""

    def __init__(
        self, field_name: str, language: str, exclusive_minimum: float, is_required: bool = True
    ):
        super().__init__(field_name, language, is_required)
        self.exclusive_minimum = exclusive_minimum

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"self.{self.field_name} <= {self.exclusive_minimum}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must be > {self.exclusive_minimum}, got {{self.{self.field_name}}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} <= {self.exclusive_minimum})",
                f'    throw new ArgumentException($"{prop_name} must be > {self.exclusive_minimum}", nameof({prop_name}));',
            ]
        return []


class ExclusiveMaximumRule(ValidationRule):
    """Validates exclusive maximum numeric value"""

    def __init__(
        self, field_name: str, language: str, exclusive_maximum: float, is_required: bool = True
    ):
        super().__init__(field_name, language, is_required)
        self.exclusive_maximum = exclusive_maximum

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"self.{self.field_name} >= {self.exclusive_maximum}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must be < {self.exclusive_maximum}, got {{self.{self.field_name}}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} >= {self.exclusive_maximum})",
                f'    throw new ArgumentException($"{prop_name} must be < {self.exclusive_maximum}", nameof({prop_name}));',
            ]
        return []


class MultipleOfRule(ValidationRule):
    """Validates that a number is a multiple of a value"""

    def __init__(self, field_name: str, language: str, multiple: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.multiple = multiple

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"self.{self.field_name} % {self.multiple} != 0"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must be a multiple of {self.multiple}, got {{self.{self.field_name}}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name} % {self.multiple} != 0)",
                f'    throw new ArgumentException($"{prop_name} must be a multiple of {self.multiple}", nameof({prop_name}));',
            ]
        return []


class MinItemsRule(ValidationRule):
    """Validates minimum array length"""

    def __init__(self, field_name: str, language: str, min_items: int, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.min_items = min_items

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"len(self.{self.field_name}) < {self.min_items}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must have at least {self.min_items} items, got {{len(self.{self.field_name})}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name}.Count < {self.min_items})",
                f'    throw new ArgumentException($"{prop_name} must have at least {self.min_items} items", nameof({prop_name}));',
            ]
        return []


class MaxItemsRule(ValidationRule):
    """Validates maximum array length"""

    def __init__(self, field_name: str, language: str, max_items: int, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.max_items = max_items

    def generate_code(self) -> List[str]:
        if self.language == "python":
            condition = f"len(self.{self.field_name}) > {self.max_items}"
            condition = self._wrap_with_none_check(condition)
            return [
                f"if {condition}:",
                f'    raise ValueError(f"{self.field_name} must have at most {self.max_items} items, got {{len(self.{self.field_name})}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            return [
                f"if ({prop_name}.Count > {self.max_items})",
                f'    throw new ArgumentException($"{prop_name} must have at most {self.max_items} items", nameof({prop_name}));',
            ]
        return []


class ArrayItemTypeRule(ValidationRule):
    """Validates array item types"""

    def __init__(self, field_name: str, language: str, item_class_name: str):
        super().__init__(field_name, language)
        self.item_class_name = item_class_name

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"for i, item in enumerate(self.{self.field_name}):",
                f"    if not isinstance(item, {self.item_class_name}):",
                f'        raise ValueError(f"{self.field_name}[{{i}}] must be a {self.item_class_name} instance, got {{type(item).__name__}}")',
            ]
        # C# doesn't need runtime item type validation due to generic types
        return []


class EnumRule(ValidationRule):
    """Validates that a value is in an enum"""

    def __init__(self, field_name: str, language: str, enum_values: List[Any]):
        super().__init__(field_name, language)
        self.enum_values = enum_values

    def generate_code(self) -> List[str]:
        if self.language == "python":
            enum_repr = ", ".join(repr(v) for v in self.enum_values)
            return [
                f"if self.{self.field_name} not in [{enum_repr}]:",
                f'    raise ValueError(f"{self.field_name} must be one of [{enum_repr}], got {{self.{self.field_name}!r}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            enum_list = ", ".join(f'"{v}"' for v in self.enum_values)
            return [
                f"var valid{prop_name}Values = new[] {{ {enum_list} }};",
                f"if (!valid{prop_name}Values.Contains({prop_name}))",
                f'    throw new ArgumentException($"{prop_name} must be one of: {enum_list}", nameof({prop_name}));',
            ]
        return []


class ConstRule(ValidationRule):
    """Validates that a value equals a constant"""

    def __init__(self, field_name: str, language: str, const_value: Any):
        super().__init__(field_name, language)
        self.const_value = const_value

    def generate_code(self) -> List[str]:
        if self.language == "python":
            return [
                f"if self.{self.field_name} != {self.const_value!r}:",
                f'    raise ValueError(f"{self.field_name} must be {self.const_value!r}, got {{self.{self.field_name}!r}}")',
            ]
        elif self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            const_repr = (
                f'"{self.const_value}"'
                if isinstance(self.const_value, str)
                else str(self.const_value)
            )
            return [
                f"if ({prop_name} != {const_repr})",
                f'    throw new ArgumentException($"{prop_name} must be {const_repr}", nameof({prop_name}));',
            ]
        return []
