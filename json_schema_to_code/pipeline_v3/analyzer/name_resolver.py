"""
Name resolver for handling naming collisions and case conversion.

Converts snake_case definition names to PascalCase class names
and handles collisions between inline objects and definitions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schema_ast.nodes import (
    AllOfNode,
    ArrayNode,
    ObjectNode,
    PropertyDef,
    SchemaAST,
    SchemaNode,
)

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


@dataclass
class NameMapping:
    """Result of name resolution."""

    # Original name -> PascalCase name
    definition_names: dict[str, str] = field(default_factory=dict)

    # (parent_class, field_name) -> inline class name
    inline_class_names: dict[tuple[str, str], str] = field(default_factory=dict)


class NameResolver:
    """Resolves class names and handles collisions."""

    # Regex for splitting words
    _WORD_PATTERN = re.compile(r"[a-z]+|[A-Z][a-z]*|[0-9]+")

    def __init__(self, language: str = "python"):
        """
        Initialize the resolver.

        Args:
            language: Target language ("python" or "cs")
        """
        self.language = language

    def resolve_names(self, ast: SchemaAST) -> NameMapping:
        """
        Resolve all names in the AST.

        Args:
            ast: The parsed schema AST

        Returns:
            NameMapping with resolved names
        """
        mapping = NameMapping()

        # First pass: convert definition names to PascalCase
        for def_node in ast.definitions:
            pascal_name = self._to_pascal_case(def_node.original_name)
            mapping.definition_names[def_node.original_name] = pascal_name

        # Second pass: find inline objects and resolve their names
        self._collect_inline_names(ast, mapping)

        return mapping

    def _collect_inline_names(self, ast: SchemaAST, mapping: NameMapping) -> None:
        """Collect inline class names from the AST."""
        # Collect from definitions
        for def_node in ast.definitions:
            parent_name = mapping.definition_names.get(def_node.original_name, def_node.original_name)
            if def_node.body:
                self._collect_inline_from_node(def_node.body, parent_name, mapping)

        # Collect from root node
        if ast.root_node:
            self._collect_inline_from_node(ast.root_node, ast.root_name, mapping)

    def _collect_inline_from_node(
        self,
        node: SchemaNode,
        parent_name: str,
        mapping: NameMapping,
    ) -> None:
        """Recursively collect inline class names from a node."""
        if isinstance(node, ObjectNode):
            for prop in node.properties:
                self._process_property_for_inline(prop, parent_name, mapping)
        elif isinstance(node, AllOfNode):
            if node.extension:
                self._collect_inline_from_node(node.extension, parent_name, mapping)
        elif isinstance(node, ArrayNode):
            if isinstance(node.items, SchemaNode):
                # Check if array items is an inline object
                if isinstance(node.items, ObjectNode) and node.items.properties:
                    # This is handled at the property level
                    pass

    def _process_property_for_inline(
        self,
        prop: PropertyDef,
        parent_name: str,
        mapping: NameMapping,
    ) -> None:
        """Process a property for inline object detection."""
        if not prop.type_node:
            return

        type_node = prop.type_node

        # Check if this is an inline object (not a $ref)
        if isinstance(type_node, ObjectNode) and type_node.properties:
            # This is an inline object - generate a unique name
            inline_name = self._generate_inline_name(parent_name, prop.name, mapping)
            mapping.inline_class_names[(parent_name, prop.name)] = inline_name

            # Recursively process the inline object's properties
            self._collect_inline_from_node(type_node, inline_name, mapping)

        elif isinstance(type_node, ArrayNode):
            # Check if array items are inline objects
            if isinstance(type_node.items, ObjectNode) and type_node.items.properties:
                inline_name = self._generate_inline_name(parent_name, prop.name, mapping)
                mapping.inline_class_names[(parent_name, prop.name)] = inline_name
                self._collect_inline_from_node(type_node.items, inline_name, mapping)

    def _generate_inline_name(
        self,
        parent_name: str,
        field_name: str,
        mapping: NameMapping,
    ) -> str:
        """Generate a unique name for an inline class."""
        base_name = self._to_pascal_case(field_name)

        # Always prefix with parent name for uniqueness
        unique_name = f"{parent_name}{base_name}"

        return unique_name

    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        if not text:
            return ""

        # Normalize separators
        normalized = text.replace("_", " ").replace("-", " ")

        # Split into words
        words = self._WORD_PATTERN.findall(normalized)

        # Capitalize and join
        result = "".join(word.capitalize() for word in words if word)

        # Handle C# reserved keywords
        if self.language == "cs" and result.lower() in CS_RESERVED_KEYWORDS:
            result = result + "Type"

        return result

    def escape_keyword(self, name: str) -> str:
        """Escape a C# reserved keyword with @ prefix."""
        if self.language == "cs" and name.lower() in CS_RESERVED_KEYWORDS:
            return f"@{name}"
        return name
