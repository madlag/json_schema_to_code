"""
Utility functions for JSON Schema to Code generator.
"""

import re

# Regex pattern to split text into words, handling camelCase boundaries
_WORD_PATTERN = re.compile(r"[a-z]+|[A-Z][a-z]*|[0-9]+")


def _normalize_separators(text: str) -> str:
    """Normalize separators (underscores, hyphens) to spaces."""
    return text.replace("_", " ").replace("-", " ")


def _split_into_words(text: str) -> list[str]:
    """Split text into words, handling camelCase boundaries."""
    return _WORD_PATTERN.findall(text)


def _capitalize_and_join(words: list[str]) -> str:
    """Capitalize each word and join them together."""
    return "".join(word.capitalize() for word in words if word)


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
    normalized = _normalize_separators(text)
    words = _split_into_words(normalized)
    return _capitalize_and_join(words)
