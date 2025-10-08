"""
Validation rule objects that generate validation code.

Each rule represents a specific validation constraint from JSON schema
and knows how to generate code for different target languages.
"""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ValidationRule(ABC):
    """Base class for all validation rules"""

    # Class-level cache for loaded string templates
    _string_templates: Dict[str, Dict[str, Any]] = {}

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
        self.use_plain_string = False

    @classmethod
    def _load_string_templates(cls, language: str) -> Dict[str, Any]:
        """
        Load string templates from JSON file for the given language.
        Results are cached to avoid repeated file I/O.

        Args:
            language: Target language ('python' or 'cs')

        Returns:
            Dictionary of string templates for all validation rules
        """
        if language not in cls._string_templates:
            template_file = Path(__file__).parent / f"validation_rules_{language}.json"
            with open(template_file, "r", encoding="utf-8") as f:
                cls._string_templates[language] = json.load(f)
        return cls._string_templates[language]

    def get_string(self, key: str, **format_params) -> Union[str, List, Dict]:
        """
        Get a string template for this validation rule and format it.

        Args:
            key: The string key to retrieve (e.g., 'error_message', 'condition')
            **format_params: Parameters to format into the string template

        Returns:
            Formatted string, list, or dict depending on the template structure
        """
        templates = self._load_string_templates(self.language)
        class_name = self.__class__.__name__

        if class_name not in templates:
            raise KeyError(f"No string templates found for {class_name} in {self.language}")

        rule_templates = templates[class_name]

        if key not in rule_templates:
            raise KeyError(f"Key '{key}' not found in templates for {class_name}")

        template = rule_templates[key]

        # Recursively format based on type
        return self._format_template(template, format_params)

    def _format_template(self, template, format_params: dict):
        """
        Recursively format a template that can be a string, list, or dict.

        Args:
            template: The template to format (string, list, or dict)
            format_params: Parameters to format into the template

        Returns:
            Formatted template with the same structure as input
        """
        if isinstance(template, str):
            return template.format(**format_params)
        elif isinstance(template, list):
            return [self._format_template(item, format_params) for item in template]
        elif isinstance(template, dict):
            return {k: self._format_template(v, format_params) for k, v in template.items()}
        else:
            return template

    def format_validation_code(
        self,
        condition: str,
        error_message: str,
        use_raw_string: bool = False,
        use_plain_string: bool = False,
        exception_type: Optional[str] = None,
        **extra_params,
    ) -> List[str]:
        """
        Format validation code using language-specific templates.

        Args:
            condition: The condition to check
            error_message: The error message to display
            use_raw_string: Whether to use raw f-string (rf"...") for Python (default: False)
            use_plain_string: Whether to use plain string (no f-string) for Python (default: False)
            exception_type: For C#, which exception type to use (default: ArgumentException)
            **extra_params: Extra parameters for language-specific formatting (e.g., prop_name for C#)

        Returns:
            List of formatted code lines
        """
        templates = self._load_string_templates(self.language)
        template = templates.get("_template", {})

        if self.language == "python":
            if_line = template.get("if_line", "if {condition}:").format(condition=condition)
            if use_plain_string:
                raise_template = "raise_line_plain"
            elif use_raw_string:
                raise_template = "raise_line_raw"
            else:
                raise_template = "raise_line"
            raise_line = template.get(raise_template, '    raise ValueError(f"{error_message}")').format(error_message=error_message)
            return [if_line, raise_line]
        elif self.language == "cs":
            if_line = template.get("if_line", "if ({condition})").format(condition=condition)
            # Choose template based on exception type
            if exception_type == "ArgumentNullException":
                throw_template = "throw_line_null"
            else:
                throw_template = "throw_line_arg_dollar"
            throw_line = template.get(
                throw_template,
                '    throw new ArgumentException($"{error_message}", nameof({prop_name}));',
            )
            throw_line = throw_line.format(error_message=error_message, **extra_params)
            return [if_line, throw_line]
        return []

    def get_field_params(self) -> Dict[str, Any]:
        """
        Get language-specific parameters for template formatting.

        Returns:
            Dictionary with field-related parameters for the current language
        """
        if self.language == "python":
            return {"field_name": self.field_name}
        elif self.language == "cs":
            return {"prop_name": self._to_pascal_case(self.field_name)}
        return {}

    @abstractmethod
    def get_template_params(self) -> Dict[str, Any]:
        """
        Get rule-specific parameters for template formatting.
        Should return parameters needed by condition and error_message templates.

        Returns:
            Dictionary with parameters specific to this validation rule
        """
        pass

    def apply_none_check(self) -> bool:
        """
        Override to indicate if None checking should be applied.
        Default is False (no None check needed).
        """
        return False

    def use_raw_string(self) -> bool:
        """
        Override to indicate if raw f-strings should be used (Python).
        Default is False.
        """
        return False

    def get_exception_type(self) -> Optional[str]:
        """
        Override to specify a custom exception type (for C#).
        Default is None (uses ArgumentException).
        """
        return None

    def generate_code(self) -> List[str]:
        """
        Generate validation code lines for this rule.
        Uses templates from JSON and parameters from get_template_params().
        """
        # Get field params (field_name or prop_name)
        params = self.get_field_params()

        # Add rule-specific params
        params.update(self.get_template_params())

        # Get condition and error message from templates
        condition_raw = self.get_string("condition", **params)
        error_message_raw = self.get_string("error_message", **params)

        # Ensure they are strings (should always be for standard validation rules)
        if not isinstance(condition_raw, str):
            raise TypeError(f"Expected condition to be a string, got {type(condition_raw)}")
        if not isinstance(error_message_raw, str):
            raise TypeError(f"Expected error_message to be a string, got {type(error_message_raw)}")

        condition: str = condition_raw
        error_message: str = error_message_raw

        # Apply None check for optional fields if needed
        if self.language == "python" and self.apply_none_check():
            condition = self._wrap_with_none_check(condition)

        # Format using language-specific templates
        use_raw = self.use_raw_string()
        use_plain = self.use_plain_string
        exception_type = self.get_exception_type()

        if self.language == "python":
            return self.format_validation_code(condition, error_message, use_raw_string=use_raw, use_plain_string=use_plain)
        elif self.language == "cs":
            return self.format_validation_code(condition, error_message, exception_type=exception_type, **params)
        return []

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


class OptionalFieldValidationRule(ValidationRule):
    """
    Base class for validation rules that need to handle optional fields.
    Automatically applies None checks for optional (non-required) fields.
    """

    def __init__(self, field_name: str, language: str, is_required: bool = True):
        super().__init__(field_name, language, is_required)

    def apply_none_check(self) -> bool:
        """Apply None check if field is not required."""
        return not self.is_required


class TypeCheckRule(ValidationRule):
    """Validates that a field has the correct type"""

    def __init__(self, field_name: str, language: str, expected_type: str):
        super().__init__(field_name, language)
        self.expected_type = expected_type

    def get_exception_type(self) -> Optional[str]:
        return "ArgumentNullException" if self.language == "cs" else None

    def get_template_params(self) -> Dict[str, Any]:
        return {"expected_type": self.expected_type}


class ReferenceTypeCheckRule(ValidationRule):
    """Validates that a field is an instance of a referenced class"""

    def __init__(self, field_name: str, language: str, class_name: str):
        super().__init__(field_name, language)
        self.class_name = class_name

    def get_template_params(self) -> Dict[str, Any]:
        return {"class_name": self.class_name}


class NonEmptyStringRule(ValidationRule):
    """Validates that a required string is not empty"""

    def __init__(self, field_name: str, language: str):
        super().__init__(field_name, language)
        self.use_plain_string = True

    def get_template_params(self) -> Dict[str, Any]:
        return {}


class PatternRule(OptionalFieldValidationRule):
    """Validates that a string matches a regex pattern"""

    def __init__(self, field_name: str, language: str, pattern: str, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.pattern = pattern

    def use_raw_string(self) -> bool:
        return True

    def get_template_params(self) -> Dict[str, Any]:
        # For raw strings (r"..."), we only need to escape quotes, not backslashes
        escaped_pattern = self.pattern.replace('"', '\\"')

        if self.language == "python":
            # Escape curly braces for f-string ({{ and }})
            error_pattern = escaped_pattern.replace("{", "{{").replace("}", "}}")
            return {"pattern": escaped_pattern, "error_pattern": error_pattern}
        else:  # C#
            return {"pattern": escaped_pattern}

    def get_string(self, key: str, **format_params):
        # Override to use error_pattern for error_message in Python
        if self.language == "python" and key == "error_message":
            # Replace pattern with error_pattern if available
            if "error_pattern" in format_params:
                format_params["pattern"] = format_params.pop("error_pattern")
        return super().get_string(key, **format_params)


class MinLengthRule(ValidationRule):
    """Validates minimum string length"""

    def __init__(self, field_name: str, language: str, min_length: int):
        super().__init__(field_name, language)
        self.min_length = min_length

    def get_template_params(self) -> Dict[str, Any]:
        return {"min_length": self.min_length}


class MaxLengthRule(ValidationRule):
    """Validates maximum string length"""

    def __init__(self, field_name: str, language: str, max_length: int):
        super().__init__(field_name, language)
        self.max_length = max_length

    def get_template_params(self) -> Dict[str, Any]:
        return {"max_length": self.max_length}


class MinimumRule(OptionalFieldValidationRule):
    """Validates minimum numeric value"""

    def __init__(self, field_name: str, language: str, minimum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.minimum = minimum

    def get_template_params(self) -> Dict[str, Any]:
        return {"minimum": self.minimum}


class MaximumRule(OptionalFieldValidationRule):
    """Validates maximum numeric value"""

    def __init__(self, field_name: str, language: str, maximum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.maximum = maximum

    def get_template_params(self) -> Dict[str, Any]:
        return {"maximum": self.maximum}


class ExclusiveMinimumRule(OptionalFieldValidationRule):
    """Validates minimum numeric value"""

    def __init__(self, field_name: str, language: str, exclusive_minimum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.exclusive_minimum = exclusive_minimum

    def get_template_params(self) -> Dict[str, Any]:
        return {"exclusive_minimum": self.exclusive_minimum}


class ExclusiveMaximumRule(OptionalFieldValidationRule):
    """Validates maximum numeric value"""

    def __init__(self, field_name: str, language: str, exclusive_maximum: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.exclusive_maximum = exclusive_maximum

    def get_template_params(self) -> Dict[str, Any]:
        return {"exclusive_maximum": self.exclusive_maximum}


class MultipleOfRule(OptionalFieldValidationRule):
    """Validates multiple of a number"""

    def __init__(self, field_name: str, language: str, multiple: float, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.multiple = multiple

    def get_template_params(self) -> Dict[str, Any]:
        return {"multiple": self.multiple}


class MinItemsRule(OptionalFieldValidationRule):
    """Validates minimum array length"""

    def __init__(self, field_name: str, language: str, min_items: int, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.min_items = min_items

    def get_template_params(self) -> Dict[str, Any]:
        return {"min_items": self.min_items}


class MaxItemsRule(OptionalFieldValidationRule):
    """Validates maximum array length"""

    def __init__(self, field_name: str, language: str, max_items: int, is_required: bool = True):
        super().__init__(field_name, language, is_required)
        self.max_items = max_items

    def get_template_params(self) -> Dict[str, Any]:
        return {"max_items": self.max_items}


class ArrayItemTypeRule(ValidationRule):
    """Validates array item types"""

    def __init__(self, field_name: str, language: str, item_class_name: str):
        super().__init__(field_name, language)
        self.item_class_name = item_class_name

    def get_template_params(self) -> Dict[str, Any]:
        return {"item_class_name": self.item_class_name}

    def generate_code(self) -> List[str]:
        # ArrayItemTypeRule uses a for loop pattern, not standard if/raise
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

    def get_template_params(self) -> Dict[str, Any]:
        if self.language == "python":
            enum_repr = ", ".join(repr(v) for v in self.enum_values)
            return {"enum_values": f"[{enum_repr}]"}
        return {}

    def generate_code(self) -> List[str]:
        # EnumRule needs special handling for C# (var declaration)
        if self.language == "cs":
            prop_name = self._to_pascal_case(self.field_name)
            enum_list = ", ".join(f'"{v}"' for v in self.enum_values)
            return [
                f"var valid{prop_name}Values = new[] {{ {enum_list} }};",
                f"if (!valid{prop_name}Values.Contains({prop_name}))",
                f'    throw new ArgumentException($"{prop_name} must be one of: {enum_list}", nameof({prop_name}));',
            ]
        # Python uses standard template
        return super().generate_code()


class ConstRule(ValidationRule):
    """Validates that a value equals a constant"""

    def __init__(self, field_name: str, language: str, const_value: Any):
        super().__init__(field_name, language)
        self.const_value = const_value

    def get_template_params(self) -> Dict[str, Any]:
        # Pass the actual value - JSON template uses {const_value!r} for Python
        if self.language == "cs":
            const_str = f'"{self.const_value}"' if isinstance(self.const_value, str) else str(self.const_value)
            return {"const_value": const_str}
        return {"const_value": self.const_value}
