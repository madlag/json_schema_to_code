"""
Reference resolver for $ref resolution.

Resolves $ref paths to their actual definitions in the schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema_ast.nodes import DefinitionNode, RefNode, SchemaAST


@dataclass
class ResolvedRef:
    """A resolved $ref."""

    target_name: str = ""  # Resolved class/type name
    target_node: DefinitionNode | None = None  # Resolved definition
    is_external: bool = False  # Whether this is an external $ref
    external_path: str = ""  # External schema path (if external)
    class_name_in_external: str = ""  # Class name in external schema


@dataclass
class ResolverContext:
    """Context for reference resolution."""

    ast: SchemaAST | None = None
    name_mapping: dict[str, str] = field(default_factory=dict)  # original -> resolved name


class ReferenceResolver:
    """Resolves $ref to actual definitions."""

    def __init__(self, ast: SchemaAST, name_mapping: dict[str, str]):
        """
        Initialize the resolver.

        Args:
            ast: The parsed schema AST
            name_mapping: Mapping from original names to PascalCase names
        """
        self.ast = ast
        self.name_mapping = name_mapping
        self._definition_cache: dict[str, DefinitionNode] = {}
        self._build_cache()

    def _build_cache(self) -> None:
        """Build a cache of definitions by name."""
        for def_node in self.ast.definitions:
            self._definition_cache[def_node.original_name] = def_node

    def resolve(self, ref_node: RefNode) -> ResolvedRef:
        """
        Resolve a $ref node to its target.

        Args:
            ref_node: The RefNode to resolve

        Returns:
            ResolvedRef with target information
        """
        ref_path = ref_node.ref_path

        # Check for external $ref
        if not ref_path.startswith("#"):
            return self._resolve_external_ref(ref_node)

        # Local $ref
        return self._resolve_local_ref(ref_node)

    def _resolve_local_ref(self, ref_node: RefNode) -> ResolvedRef:
        """Resolve a local $ref (starts with #)."""
        ref_path = ref_node.ref_path

        # Extract the definition name from path
        # e.g., "#/definitions/MyClass" or "#/$defs/MyClass"
        parts = ref_path.split("/")
        if len(parts) >= 3 and parts[1] in ("definitions", "$defs"):
            def_name = parts[2]
        else:
            def_name = parts[-1]

        # Look up in cache
        def_node = self._definition_cache.get(def_name)

        # Get the resolved name
        target_name = self.name_mapping.get(def_name, def_name)

        # Check for class name override
        if ref_node.class_name_override:
            target_name = ref_node.class_name_override

        return ResolvedRef(
            target_name=target_name,
            target_node=def_node,
            is_external=False,
        )

    def _resolve_external_ref(self, ref_node: RefNode) -> ResolvedRef:
        """Resolve an external $ref (doesn't start with #)."""
        ref_path = ref_node.ref_path

        # Parse: "/path/to/schema#/$defs/ClassName"
        if "#/$defs/" in ref_path:
            path_part, class_name = ref_path.split("#/$defs/", 1)
        elif "#/definitions/" in ref_path:
            path_part, class_name = ref_path.split("#/definitions/", 1)
        else:
            # Just a schema reference without fragment
            path_part = ref_path
            class_name = ref_path.split("/")[-1].replace(".json", "")

        # Check for class name override
        if ref_node.class_name_override:
            class_name = ref_node.class_name_override

        return ResolvedRef(
            target_name=class_name,
            target_node=None,  # External, not in our AST
            is_external=True,
            external_path=path_part,
            class_name_in_external=class_name,
        )

    def get_definition(self, name: str) -> DefinitionNode | None:
        """Get a definition by original name."""
        return self._definition_cache.get(name)
