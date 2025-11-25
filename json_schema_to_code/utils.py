"""
Utility functions for JSON Schema to Code generator.
"""

import re


def snake_to_pascal_case(text: str) -> str:
    """Convert snake_case, camelCase, or space-separated text to PascalCase.

    Examples:
        "first_name" -> "FirstName"
        "FIRST_NAME" -> "FirstName"
        "actionTemplate" -> "ActionTemplate"
        "first 3 rows" -> "First3Rows"
        "ABC" -> "Abc"
        "Full" -> "Full"

    Args:
        text: The text to convert (snake_case, camelCase, UPPER_SNAKE_CASE, or space-separated)

    Returns:
        PascalCase string
    """
    if not text:
        return ""
    # First, replace underscores, hyphens, and spaces with a delimiter
    text = text.replace("_", " ").replace("-", " ")
    # Split on camelCase boundaries (lowercase/digit followed by uppercase)
    # This regex finds positions where we should split: before uppercase letters
    # that follow lowercase letters or digits
    words = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text)
    # Capitalize each word and join
    return "".join(word.capitalize() for word in words if word)
