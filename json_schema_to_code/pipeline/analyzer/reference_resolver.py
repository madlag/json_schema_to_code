"""
Reference resolver for $ref resolution.

Resolves $ref paths to their actual definitions in the schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..schema_ast.nodes import DefinitionNode, RefNode, SchemaAST


@dataclass
class ResolvedRef:
    """A resolved $ref."""

    target_name: str = ""  # Resolved class/type name
    target_node: DefinitionNode | None = None  # Resolved definition
    is_external: bool = False  # Whether this is an external $ref
    external_path: str = ""  # External schema path (if external)
    class_name_in_external: str = ""  # Class name in external schema
    external_definition: dict | None = None  # The raw definition dict from external schema


@dataclass
class ResolverContext:
    """Context for reference resolution."""

    ast: SchemaAST | None = None
    name_mapping: dict[str, str] = field(default_factory=dict)  # original -> resolved name


class ReferenceResolver:
    """Resolves $ref to actual definitions."""

    def __init__(self, ast: SchemaAST, name_mapping: dict[str, str], schema_base_path: str = ""):
        """
        Initialize the resolver.

        Args:
            ast: The parsed schema AST
            name_mapping: Mapping from original names to PascalCase names
            schema_base_path: Base path for resolving external schema files
        """
        self.ast = ast
        self.name_mapping = name_mapping
        self.schema_base_path = Path(schema_base_path) if schema_base_path else None
        self._definition_cache: dict[str, DefinitionNode] = {}
        self._external_schema_cache: dict[str, dict] = {}  # Cache loaded external schemas
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

        # Try to load external definition if schema_base_path is set
        external_definition = None
        if self.schema_base_path:
            external_definition = self._load_external_definition(path_part, class_name)

        return ResolvedRef(
            target_name=class_name,
            target_node=None,  # External, not in our AST
            is_external=True,
            external_path=path_part,
            class_name_in_external=class_name,
            external_definition=external_definition,
        )

    def _load_external_definition(self, schema_path: str, class_name: str) -> dict | None:
        """Load a definition from an external schema file."""
        # Try different file extensions
        base_path = schema_path.lstrip("/")
        possible_paths = [
            self.schema_base_path / f"{base_path}.jinja.json",
            self.schema_base_path / f"{base_path}.json",
            self.schema_base_path / f"{base_path}_schema.jinja.json",
            self.schema_base_path / f"{base_path}_schema.json",
        ]

        schema_data = None
        for path in possible_paths:
            if path.exists():
                # Use cache
                cache_key = str(path)
                if cache_key not in self._external_schema_cache:
                    with open(path) as f:
                        self._external_schema_cache[cache_key] = json.load(f)
                schema_data = self._external_schema_cache[cache_key]
                break

        if not schema_data:
            return None

        # Extract the definition
        defs = schema_data.get("$defs") or schema_data.get("definitions") or {}
        return defs.get(class_name)

    def get_definition(self, name: str) -> DefinitionNode | None:
        """Get a definition by original name."""
        return self._definition_cache.get(name)
