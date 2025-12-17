"""
JSON Schema parser that builds an AST.

Phase 1 of the pipeline: Parse JSON Schema into an AST without
resolving references or doing language-specific processing.
"""

from __future__ import annotations

from typing import Any

from .nodes import (
    AllOfNode,
    ArrayNode,
    ConstNode,
    DefinitionNode,
    EnumNode,
    ObjectNode,
    PrimitiveNode,
    PropertyDef,
    RefNode,
    SchemaAST,
    SchemaNode,
    UnionNode,
)


class SchemaParser:
    """Parses JSON Schema into an AST."""

    # Primitive type names
    PRIMITIVE_TYPES = {"string", "integer", "number", "boolean", "null", "object"}

    def parse(self, schema: dict[str, Any], root_name: str) -> SchemaAST:
        """
        Parse a JSON Schema into an AST.

        Args:
            schema: The JSON Schema dictionary
            root_name: Name for the root class (if schema has properties)

        Returns:
            SchemaAST with parsed definitions and optional root node
        """
        ast = SchemaAST(
            root_name=root_name,
            raw_schema=schema,
        )

        # Parse definitions
        definitions = schema.get("definitions") or schema.get("$defs") or {}
        for name, def_schema in definitions.items():
            # Skip comment fields (strings) and _comment prefixed keys
            if isinstance(def_schema, str) or name.startswith("_comment"):
                continue

            # Skip external $ref definitions
            if self._is_external_ref(def_schema):
                continue

            def_node = DefinitionNode(
                name=name,
                original_name=name,
                body=self._parse_schema_node(def_schema, f"#/definitions/{name}"),
                source_path=f"#/definitions/{name}",
            )
            ast.definitions.append(def_node)

        # Parse root node if it has properties
        if "properties" in schema:
            ast.root_node = self._parse_schema_node(schema, "#")

        return ast

    def _is_external_ref(self, value: Any) -> bool:
        """Check if a value is an external $ref (not a local reference)."""
        return isinstance(value, dict) and "$ref" in value and not value["$ref"].startswith("#")

    def _parse_schema_node(self, schema: dict[str, Any], path: str) -> SchemaNode:
        """
        Parse a schema node recursively.

        Args:
            schema: The schema dictionary
            path: Current path in schema (for error messages)

        Returns:
            Appropriate SchemaNode subclass
        """
        # Extract common metadata
        metadata = self._extract_metadata(schema)

        # Handle $ref
        if "$ref" in schema:
            return self._parse_ref_node(schema, path, metadata)

        # Handle const
        if "const" in schema:
            return self._parse_const_node(schema, path, metadata)

        # Handle oneOf/anyOf
        if "oneOf" in schema or "anyOf" in schema:
            return self._parse_union_node(schema, path, metadata)

        # Handle allOf (inheritance)
        if "allOf" in schema:
            return self._parse_allof_node(schema, path, metadata)

        # Handle enum definitions that have x-enum-members (should become real enums)
        # This takes priority even if "type" is present
        if "enum" in schema and "x-enum-members" in schema:
            return self._parse_enum_node(schema, path, metadata)

        # Handle type-based parsing (before enum, to match original codegen.py)
        # When a property has both "type" and "enum" but no x-enum-members,
        # treat it as the type (the enum values are just documentation/validation)
        # Note: For definitions with type: "string" + enum: [...], we still parse as type
        # but store the enum info in metadata for the analyzer to decide
        if "type" in schema:
            node = self._parse_type_node(schema, path, metadata)
            # Store enum values in metadata for string types (analyzer will use for Python)
            if "enum" in schema and schema.get("type") == "string":
                node.metadata["enum"] = schema["enum"]
            return node

        # Handle standalone enum (without type and without x-enum-members)
        if "enum" in schema:
            return self._parse_enum_node(schema, path, metadata)

        # Handle object with properties but no type
        if "properties" in schema:
            return self._parse_object_node(schema, path, metadata)

        # Fallback: treat as generic object
        return PrimitiveNode(
            type_name="object",
            source_path=path,
            metadata=metadata,
        )

    def _extract_metadata(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Extract x-* extension metadata from schema."""
        metadata = {}
        for key, value in schema.items():
            if key.startswith("x-"):
                metadata[key] = value
        return metadata

    def _parse_ref_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> RefNode:
        """Parse a $ref node."""
        ref_path = schema["$ref"]
        class_name_override = schema.get("x-ref-class-name")

        node = RefNode(
            ref_path=ref_path,
            class_name_override=class_name_override,
            source_path=path,
            metadata=metadata,
        )

        # Check for default value on $ref
        if "default" in schema:
            node.metadata["default"] = schema["default"]

        return node

    def _parse_const_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> ConstNode:
        """Parse a const node."""
        value = schema["const"]
        inferred_type = self._infer_type(value)

        return ConstNode(
            value=value,
            inferred_type=inferred_type,
            source_path=path,
            metadata=metadata,
        )

    def _parse_enum_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> EnumNode:
        """Parse an enum node."""
        values = schema["enum"]
        inferred_type = self._infer_type(values[0]) if values else "string"

        # Get custom member names from x-enum-members
        member_names = schema.get("x-enum-members", {})

        return EnumNode(
            values=values,
            inferred_type=inferred_type,
            member_names=member_names,
            source_path=path,
            metadata=metadata,
        )

    def _parse_union_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> UnionNode:
        """Parse a oneOf or anyOf union node."""
        if "oneOf" in schema:
            union_type = "oneOf"
            variants_schema = schema["oneOf"]
        else:
            union_type = "anyOf"
            variants_schema = schema["anyOf"]

        variants = []
        for i, variant in enumerate(variants_schema):
            variant_path = f"{path}/{union_type}/{i}"
            variants.append(self._parse_schema_node(variant, variant_path))

        node = UnionNode(
            variants=variants,
            union_type=union_type,
            source_path=path,
            metadata=metadata,
        )

        # Check for default value
        if "default" in schema:
            node.metadata["default"] = schema["default"]

        return node

    def _parse_allof_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> AllOfNode:
        """Parse an allOf node (inheritance)."""
        allof = schema["allOf"]

        # First element should be a $ref to base class
        base_ref = None
        extension = None

        if len(allof) >= 1 and "$ref" in allof[0]:
            base_ref = RefNode(
                ref_path=allof[0]["$ref"],
                source_path=f"{path}/allOf/0",
            )

        if len(allof) >= 2:
            ext_schema = allof[1]
            extension_node = self._parse_schema_node(ext_schema, f"{path}/allOf/1")
            if isinstance(extension_node, ObjectNode):
                extension = extension_node
            else:
                # Wrap non-object extension in ObjectNode
                extension = ObjectNode(
                    source_path=f"{path}/allOf/1",
                    metadata=extension_node.metadata,
                )

        return AllOfNode(
            base_ref=base_ref,
            extension=extension,
            source_path=path,
            metadata=metadata,
        )

    def _parse_type_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> SchemaNode:
        """Parse a type-based node."""
        type_value = schema["type"]

        # Handle array of types (union)
        if isinstance(type_value, list):
            # Single-element type array is not a union
            if len(type_value) == 1:
                type_value = type_value[0]
            else:
                return self._parse_type_union(schema, type_value, path, metadata)

        # Handle array type
        if type_value == "array":
            return self._parse_array_node(schema, path, metadata)

        # Handle object type
        if type_value == "object":
            return self._parse_object_node(schema, path, metadata)

        # Handle primitive types
        return self._parse_primitive_node(schema, type_value, path, metadata)

    def _parse_type_union(
        self,
        schema: dict[str, Any],
        types: list[str],
        path: str,
        metadata: dict[str, Any],
    ) -> UnionNode:
        """Parse a union of types (e.g., ["string", "null"])."""
        variants = []
        for t in types:
            variant_schema = {"type": t}
            variants.append(self._parse_schema_node(variant_schema, f"{path}/type/{t}"))

        node = UnionNode(
            variants=variants,
            union_type="typeArray",  # Distinguish from explicit oneOf/anyOf
            source_path=path,
            metadata=metadata,
        )

        # Carry over default value
        if "default" in schema:
            node.metadata["default"] = schema["default"]

        return node

    def _parse_array_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> ArrayNode:
        """Parse an array type node."""
        items_schema = schema.get("items")
        items = None

        if items_schema is not None:
            if isinstance(items_schema, list):
                # Tuple type
                items = [self._parse_schema_node(item, f"{path}/items/{i}") for i, item in enumerate(items_schema)]
            else:
                # Single item type
                items = self._parse_schema_node(items_schema, f"{path}/items")

        node = ArrayNode(
            items=items,
            min_items=schema.get("minItems"),
            max_items=schema.get("maxItems"),
            source_path=path,
            metadata=metadata,
        )

        # Carry over default value
        if "default" in schema:
            node.metadata["default"] = schema["default"]

        return node

    def _parse_object_node(self, schema: dict[str, Any], path: str, metadata: dict[str, Any]) -> ObjectNode:
        """Parse an object type node."""
        properties = []
        required_fields = schema.get("required", [])

        for prop_name, prop_schema in schema.get("properties", {}).items():
            prop_path = f"{path}/properties/{prop_name}"
            prop_node = self._parse_schema_node(prop_schema, prop_path)

            has_default = "default" in prop_schema
            default_value = prop_schema.get("default")

            prop_def = PropertyDef(
                name=prop_name,
                type_node=prop_node,
                is_required=prop_name in required_fields,
                default_value=default_value,
                has_default=has_default,
                source_path=prop_path,
            )
            properties.append(prop_def)

        # Extract C# interface info
        implements = schema.get("x-csharp-implements")
        interface_properties = schema.get("x-csharp-properties", {})

        return ObjectNode(
            properties=properties,
            required=required_fields,
            implements=implements,
            interface_properties=interface_properties,
            source_path=path,
            metadata=metadata,
        )

    def _parse_primitive_node(
        self,
        schema: dict[str, Any],
        type_name: str,
        path: str,
        metadata: dict[str, Any],
    ) -> PrimitiveNode:
        """Parse a primitive type node."""
        node = PrimitiveNode(
            type_name=type_name,
            source_path=path,
            metadata=metadata,
        )

        # Extract validation constraints
        if type_name == "string":
            node.min_length = schema.get("minLength")
            node.max_length = schema.get("maxLength")
            node.pattern = schema.get("pattern")

        if type_name in ("integer", "number"):
            node.minimum = schema.get("minimum")
            node.maximum = schema.get("maximum")
            node.exclusive_minimum = schema.get("exclusiveMinimum")
            node.exclusive_maximum = schema.get("exclusiveMaximum")
            node.multiple_of = schema.get("multipleOf")

        # Carry over default value
        if "default" in schema:
            node.metadata["default"] = schema["default"]

        return node

    def _infer_type(self, value: Any) -> str:
        """Infer the JSON Schema type from a Python value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if value is None:
            return "null"
        return "object"
