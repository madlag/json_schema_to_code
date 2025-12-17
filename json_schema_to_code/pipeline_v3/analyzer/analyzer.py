"""
Schema analyzer that transforms AST to IR.

Phase 2 of the pipeline: Resolve references, handle inheritance,
and build the IR ready for code generation.
"""

from __future__ import annotations

from typing import Any

from ..config import CodeGeneratorConfig
from ..schema_ast.nodes import (
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
from .ir_nodes import (
    IR,
    ClassDef,
    EnumDef,
    FieldDef,
    ImportDef,
    TypeAlias,
    TypeKind,
    TypeRef,
)
from .name_resolver import NameMapping, NameResolver
from .reference_resolver import ReferenceResolver, ResolvedRef

# Import validation generator from existing code
try:
    from ...validator import ValidationGenerator
except ImportError:
    ValidationGenerator = None


class SchemaAnalyzer:
    """Analyzes schema AST and builds IR."""

    def __init__(self, language: str, config: CodeGeneratorConfig):
        """
        Initialize the analyzer.

        Args:
            language: Target language ("python" or "cs")
            config: Code generation configuration
        """
        self.language = language
        self.config = config
        self.name_resolver = NameResolver(language)

        # Initialize validation generator if enabled
        self.validator = None
        if config.add_validation and ValidationGenerator:
            self.validator = ValidationGenerator(language)
        self.needs_re_import = False

        # Will be set during analysis
        self.ast: SchemaAST | None = None
        self.name_mapping: NameMapping | None = None
        self.ref_resolver: ReferenceResolver | None = None

        # Track subclass relationships
        # base -> [(name, discriminator), ...]
        self.subclasses: dict[str, list[tuple[str, str]]] = {}
        self.base_class: dict[str, str] = {}  # class -> base

        # Track type aliases needed
        self.type_aliases: dict[str, TypeAlias] = {}

        # Track required imports
        self.required_imports: set[str] = set()
        self.python_imports: set[tuple[str, str]] = set()

    def analyze(self, ast: SchemaAST) -> IR:
        """
        Analyze the AST and build IR.

        Args:
            ast: The parsed schema AST

        Returns:
            IR ready for code generation
        """
        self.ast = ast
        self.name_mapping = self.name_resolver.resolve_names(ast)
        self.ref_resolver = ReferenceResolver(ast, self.name_mapping.definition_names)

        ir = IR(root_name=ast.root_name)
        ir.name_mapping = self.name_mapping.definition_names.copy()

        # First pass: identify inheritance relationships
        self._build_inheritance_graph()

        # Second pass: build class definitions
        classes_to_generate = self._collect_classes_to_generate()
        for def_node in classes_to_generate:
            class_def = self._analyze_definition(def_node)
            if class_def:
                ir.classes.append(class_def)

        # Add inline classes
        inline_classes = self._collect_inline_classes()
        for class_def in inline_classes:
            ir.classes.append(class_def)

        # Add root class if needed
        if ast.root_node:
            root_class = self._analyze_root_node()
            if root_class:
                ir.classes.insert(0, root_class)

        # Add type aliases
        ir.type_aliases = list(self.type_aliases.values())

        # Sort type aliases by forward reference
        simple_aliases = [a for a in ir.type_aliases if not a.has_forward_refs]
        forward_aliases = [a for a in ir.type_aliases if a.has_forward_refs]
        ir.type_aliases = simple_aliases  # Simple ones go in prefix

        # Forward reference aliases get added after classes
        for alias in forward_aliases:
            ir.type_aliases.append(alias)

        # Build imports
        ir.imports = self._build_imports()

        return ir

    def _build_inheritance_graph(self) -> None:
        """Build the inheritance graph from allOf and anyOf/oneOf relationships."""
        for def_node in self.ast.definitions:
            # Handle allOf (explicit inheritance)
            if isinstance(def_node.body, AllOfNode):
                self._process_allof_inheritance(def_node)

            # Handle anyOf/oneOf discriminated unions (C# only)
            # For anyOf/oneOf with all $refs, the union type becomes a base class
            if self.language == "cs" and isinstance(def_node.body, UnionNode):
                self._process_union_discriminated_type(def_node)

    def _process_allof_inheritance(self, def_node: DefinitionNode) -> None:
        """Process allOf inheritance relationship."""
        allof = def_node.body
        if not isinstance(allof, AllOfNode) or not allof.base_ref:
            return

        # Resolve the base class
        resolved = self.ref_resolver.resolve(allof.base_ref)
        base_class_name = resolved.target_name

        # Get this class's name
        class_name = self.name_mapping.definition_names.get(def_node.original_name, def_node.original_name)

        # Find discriminator value from "type" const in extension
        discriminator = class_name
        if allof.extension:
            for prop in allof.extension.properties:
                if prop.name == "type" and isinstance(prop.type_node, ConstNode):
                    discriminator = prop.type_node.value
                    break

        # Register the relationship
        if base_class_name not in self.subclasses:
            self.subclasses[base_class_name] = []

        if class_name not in self.config.ignore_classes:
            self.subclasses[base_class_name].append((class_name, discriminator))

        self.base_class[class_name] = base_class_name

    def _process_union_discriminated_type(self, def_node: DefinitionNode) -> None:
        """Process anyOf/oneOf as discriminated union for C#."""
        union = def_node.body
        if not isinstance(union, UnionNode):
            return

        # Check if all variants are $refs
        all_refs = all(isinstance(v, RefNode) for v in union.variants)
        if not all_refs or len(union.variants) < 2:
            return

        # Check if all referenced definitions actually exist in this schema
        # If they don't, this isn't a discriminated union we can generate
        all_exist = True
        for variant in union.variants:
            if isinstance(variant, RefNode):
                ref_name = variant.ref_path.split("/")[-1]
                subtype_def = self.ref_resolver.get_definition(ref_name)
                if not subtype_def:
                    all_exist = False
                    break

        if not all_exist:
            return

        # This is a discriminated union - the base type name
        base_class_name = self.name_mapping.definition_names.get(def_node.original_name, def_node.original_name)

        if base_class_name not in self.subclasses:
            self.subclasses[base_class_name] = []

        # Each $ref is a subtype
        for variant in union.variants:
            if not isinstance(variant, RefNode):
                continue

            resolved = self.ref_resolver.resolve(variant)
            subtype_name = resolved.target_name

            # Find discriminator value by looking at the subtype's "type" const property
            discriminator = subtype_name
            subtype_def = self.ref_resolver.get_definition(variant.ref_path.split("/")[-1])
            if subtype_def and isinstance(subtype_def.body, ObjectNode):
                for prop in subtype_def.body.properties:
                    if prop.name == "type" and isinstance(prop.type_node, ConstNode):
                        discriminator = prop.type_node.value
                        break

            if subtype_name not in self.config.ignore_classes:
                self.subclasses[base_class_name].append((subtype_name, discriminator))
                self.base_class[subtype_name] = base_class_name

    def _collect_classes_to_generate(self) -> list[DefinitionNode]:
        """Collect definitions in the order they should be generated."""
        # Use config order if specified
        ordered = []
        remaining = {d.original_name: d for d in self.ast.definitions}

        # First, add in specified order
        for name in self.config.order_classes:
            if name in remaining:
                ordered.append(remaining.pop(name))

        # Then add remaining in definition order
        for def_node in self.ast.definitions:
            if def_node.original_name in remaining:
                ordered.append(remaining.pop(def_node.original_name))

        return ordered

    def _analyze_definition(self, def_node: DefinitionNode) -> ClassDef | None:
        """Analyze a single definition and create ClassDef."""
        class_name = self.name_mapping.definition_names.get(def_node.original_name, def_node.original_name)

        if class_name in self.config.ignore_classes:
            return None

        body = def_node.body

        # Handle enum types
        if isinstance(body, EnumNode):
            return self._analyze_enum_definition(def_node, body, class_name)

        # Handle union types (oneOf/anyOf with all $refs)
        if isinstance(body, UnionNode):
            return self._analyze_union_definition(def_node, body, class_name)

        # Handle allOf (inheritance)
        if isinstance(body, AllOfNode):
            return self._analyze_allof_definition(def_node, body, class_name)

        # Handle object types
        if isinstance(body, ObjectNode):
            return self._analyze_object_definition(def_node, body, class_name)

        # Handle primitive base types
        if isinstance(body, PrimitiveNode):
            return self._analyze_primitive_definition(def_node, body, class_name)

        return None

    def _analyze_enum_definition(self, def_node: DefinitionNode, enum_node: EnumNode, class_name: str) -> ClassDef | None:
        """Analyze an enum definition."""
        # Build enum member names
        members = {}
        for value in enum_node.values:
            if value in enum_node.member_names:
                member_name = enum_node.member_names[value]
            else:
                # Auto-generate member name
                member_name = self._to_enum_member_name(str(value))
            members[member_name] = value

        enum_def = EnumDef(
            name=class_name,
            original_name=def_node.original_name,
            value_type=enum_node.inferred_type,
            members=members,
        )

        # For C#, string enums become enum classes
        # For Python, they become Enum subclasses
        class_def = ClassDef(
            name=class_name,
            original_name=def_node.original_name,
            is_enum=True,
            enum_def=enum_def,
        )

        return class_def

    def _analyze_union_definition(self, def_node: DefinitionNode, union_node: UnionNode, class_name: str) -> ClassDef | None:
        """Analyze a union type definition (oneOf/anyOf)."""
        # Check if all variants are $refs (discriminated union pattern)
        all_refs = all(isinstance(v, RefNode) for v in union_node.variants)

        if all_refs and len(union_node.variants) > 1:
            # This is a type alias (union of classes)
            union_types = []
            for variant in union_node.variants:
                if isinstance(variant, RefNode):
                    resolved = self.ref_resolver.resolve(variant)
                    union_types.append(resolved.target_name)

            # Create type alias
            alias = TypeAlias(
                name=class_name,
                union_components=sorted(union_types),
            )
            self.type_aliases[class_name] = alias

            # For C#, we still generate a base class if discriminated
            if self.language == "cs" and class_name in self.subclasses:
                return ClassDef(
                    name=class_name,
                    original_name=def_node.original_name,
                    subclasses=self.subclasses.get(class_name, []),
                )

            return None

        # Not all refs - treat as union type field
        return None

    def _analyze_allof_definition(self, def_node: DefinitionNode, allof: AllOfNode, class_name: str) -> ClassDef:
        """Analyze an allOf (inheritance) definition."""
        class_def = ClassDef(
            name=class_name,
            original_name=def_node.original_name,
        )

        # Set base class
        if allof.base_ref:
            resolved = self.ref_resolver.resolve(allof.base_ref)
            class_def.base_class = resolved.target_name

            # Get base class properties to pass to constructor
            base_def = self.ref_resolver.get_definition(allof.base_ref.ref_path.split("/")[-1])
            if base_def and isinstance(base_def.body, ObjectNode):
                class_def.base_fields = self._analyze_base_properties(base_def.body, allof.extension, class_name)

        # Add subclasses if this is a base class
        class_def.subclasses = self.subclasses.get(class_name, [])

        # Analyze extension properties
        if allof.extension:
            class_def.fields = self._analyze_properties(allof.extension, class_name)

        # Build constructor fields (non-const fields)
        class_def.constructor_fields = [f for f in class_def.fields if not f.is_const]

        return class_def

    def _analyze_base_properties(
        self,
        base_obj: ObjectNode,
        extension: ObjectNode | None,
        class_name: str,
    ) -> list[FieldDef]:
        """Analyze base class properties for constructor passing."""
        base_fields = []

        for base_prop in base_obj.properties:
            # Check if base property is already a const
            is_base_const = isinstance(base_prop.type_node, ConstNode)

            # Check if this property is overridden with a const in extension
            is_overridden_const = False
            override_value = None
            if extension:
                for ext_prop in extension.properties:
                    if ext_prop.name == base_prop.name:
                        if isinstance(ext_prop.type_node, ConstNode):
                            is_overridden_const = True
                            override_value = ext_prop.type_node.value
                        break

            field_def = FieldDef(
                name=base_prop.name,
                original_name=base_prop.name,
                is_required=base_prop.is_required,
            )

            # Set type_ref for C# constructor parameter types
            if base_prop.type_node:
                field_def.type_ref = self._analyze_type(base_prop.type_node, base_prop.name, class_name, base_prop.is_required)

            # Mark as const based on override or base status
            # is_const = True means exclude from constructor params
            # For base const: pass variable name in base call
            # For overridden const: pass literal value in base call
            if is_overridden_const:
                field_def.default_value = override_value
                field_def.has_default = True
                field_def.is_const = True
                field_def.is_overridden_const = True  # Flag for using literal
            elif is_base_const:
                # Base class const - exclude from constructor params
                # but pass variable name in base call
                field_def.is_const = True
                field_def.is_overridden_const = False  # Flag for using variable name

            base_fields.append(field_def)

        return base_fields

    def _analyze_object_definition(self, def_node: DefinitionNode, obj: ObjectNode, class_name: str) -> ClassDef:
        """Analyze an object type definition."""
        class_def = ClassDef(
            name=class_name,
            original_name=def_node.original_name,
            subclasses=self.subclasses.get(class_name, []),
        )

        # Check if this class is a subtype (from discriminated union or allOf)
        if class_name in self.base_class:
            class_def.base_class = self.base_class[class_name]

        # C# interface implementation
        if obj.implements:
            class_def.implements = obj.implements
            class_def.interface_properties = obj.interface_properties

        # Analyze properties
        class_def.fields = self._analyze_properties(obj, class_name)

        # Build constructor fields
        class_def.constructor_fields = [f for f in class_def.fields if not f.is_const and f.name not in self.config.global_ignore_fields]

        # Generate validation code if enabled
        if self.validator:
            class_def.validation_code = self._generate_validation_code(obj, class_def)

        return class_def

    def _analyze_primitive_definition(self, def_node: DefinitionNode, prim: PrimitiveNode, class_name: str) -> ClassDef | None:
        """Analyze a primitive type definition (rare case)."""
        # Check if this is a string enum (type: "string" with enum in metadata)
        # For both Python and C#: generate enum class
        if prim.type_name == "string" and "enum" in prim.metadata:
            enum_values = prim.metadata["enum"]
            members = {self._to_enum_member_name(str(v)): v for v in enum_values}

            enum_def = EnumDef(
                name=class_name,
                original_name=def_node.original_name,
                value_type="string",
                members=members,
            )

            return ClassDef(
                name=class_name,
                original_name=def_node.original_name,
                is_enum=True,
                enum_def=enum_def,
            )

        # This is typically used for type aliases to primitives
        return None

    def _analyze_properties(self, obj: ObjectNode, parent_class: str) -> list[FieldDef]:
        """Analyze properties and create FieldDefs."""
        fields = []

        for prop in obj.properties:
            if prop.name in self.config.global_ignore_fields:
                continue

            field_def = self._analyze_property(prop, parent_class)
            fields.append(field_def)

        return fields

    def _analyze_property(self, prop: PropertyDef, parent_class: str) -> FieldDef:
        """Analyze a single property."""
        field_def = FieldDef(
            name=prop.name,
            original_name=prop.name,
            is_required=prop.is_required,
            has_default=prop.has_default,
            default_value=prop.default_value,
        )

        # Escape C# keywords
        if self.language == "cs":
            escaped = self.name_resolver.escape_keyword(prop.name)
            if escaped != prop.name:
                field_def.escaped_name = escaped

        # Analyze type
        if prop.type_node:
            field_def.type_ref = self._analyze_type(
                prop.type_node,
                prop.name,
                parent_class,
                prop.is_required,
            )

            # If field has a non-null default value, it shouldn't be nullable
            # The default provides the value, so no need for null
            # But if default is None/null, keep nullable
            if prop.has_default and field_def.type_ref and prop.default_value is not None:
                field_def.type_ref.is_nullable = False

            # Check for const type
            if isinstance(prop.type_node, ConstNode):
                field_def.is_const = True
                field_def.default_value = prop.type_node.value
                field_def.has_default = True

            # Add comment for standalone enum nodes (enum without type)
            # The original codegen.py only adds comments for pure enum fields,
            # not for fields with "type" + "enum" (those go through the type path)
            if isinstance(prop.type_node, EnumNode):
                values_str = ", ".join(f'"{v}"' for v in prop.type_node.values)
                comment_prefix = "#" if self.language == "python" else "//"
                field_def.comment = f"  {comment_prefix} Allowed values: {values_str}"

        return field_def

    def _analyze_type(
        self,
        node: SchemaNode,
        field_name: str,
        parent_class: str,
        is_required: bool,
    ) -> TypeRef:
        """Analyze a type node and create TypeRef."""
        if isinstance(node, RefNode):
            return self._analyze_ref_type(node, is_required)

        if isinstance(node, PrimitiveNode):
            return self._analyze_primitive_type(node, is_required)

        if isinstance(node, ConstNode):
            return self._analyze_const_type(node)

        if isinstance(node, EnumNode):
            return self._analyze_enum_type(node)

        if isinstance(node, ArrayNode):
            return self._analyze_array_type(node, field_name, parent_class, is_required)

        if isinstance(node, ObjectNode):
            # Objects without properties become Any (matching original codegen.py)
            if not node.properties:
                self.required_imports.add("Any")
                type_ref = TypeRef(kind=TypeKind.ANY, name="Any")
                # Check if there's a default value - if so, don't make nullable
                has_default = "default" in node.metadata
                if not is_required and not has_default:
                    type_ref.is_nullable = True
                return type_ref
            return self._analyze_inline_object_type(node, field_name, parent_class, is_required)

        if isinstance(node, UnionNode):
            return self._analyze_union_type(node, field_name, is_required)

        # Fallback
        return TypeRef(kind=TypeKind.ANY, name="Any")

    def _analyze_ref_type(self, node: RefNode, is_required: bool) -> TypeRef:
        """Analyze a $ref type."""
        resolved = self.ref_resolver.resolve(node)

        type_ref = TypeRef(
            kind=TypeKind.CLASS,
            name=resolved.target_name,
        )

        # Check for quoted types (forward references)
        if resolved.target_name in self.config.quoted_types_for_python:
            type_ref.is_quoted = True

        # Handle default value on $ref
        if "default" in node.metadata:
            type_ref.has_default = True
            type_ref.default_value = node.metadata["default"]
        elif not is_required:
            # For Python: don't make nullable, will use default_factory instead
            # For C#: make nullable
            if self.language == "cs":
                type_ref.is_nullable = True
            # For Python, leave is_nullable=False but mark as needing default_factory
            # The backend will detect this from is_required=False and generate default_factory

        # Register external import for Python
        if resolved.is_external and self.language == "python":
            self._register_external_import(resolved)

        return type_ref

    def _analyze_primitive_type(self, node: PrimitiveNode, is_required: bool) -> TypeRef:
        """Analyze a primitive type."""
        type_name = node.type_name

        # Map to language type
        kind = TypeKind.PRIMITIVE
        if type_name == "object":
            kind = TypeKind.ANY
            type_name = "Any"
            self.required_imports.add("any")

        type_ref = TypeRef(kind=kind, name=type_name)

        # Handle default value
        if "default" in node.metadata:
            type_ref.has_default = True
            type_ref.default_value = node.metadata["default"]
        elif not is_required:
            type_ref.is_nullable = True

        return type_ref

    def _analyze_const_type(self, node: ConstNode) -> TypeRef:
        """Analyze a const type."""
        return TypeRef(
            kind=TypeKind.CONST,
            name=node.inferred_type,
            const_value=node.value,
            has_default=True,
            default_value=node.value,
        )

    def _analyze_enum_type(self, node: EnumNode) -> TypeRef:
        """Analyze an inline enum type."""
        type_ref = TypeRef(
            kind=TypeKind.ENUM,
            name=node.inferred_type,
            enum_values=node.values,
            enum_member_names=node.member_names,
        )
        return type_ref

    def _analyze_array_type(
        self,
        node: ArrayNode,
        field_name: str,
        parent_class: str,
        is_required: bool,
    ) -> TypeRef:
        """Analyze an array type."""
        # Determine if this is a tuple or list
        is_tuple = isinstance(node.items, list) and node.min_items == node.max_items and self.config.use_tuples

        if is_tuple and isinstance(node.items, list):
            # Tuple type
            self.required_imports.add("tuple")
            item_types = []
            for item in node.items:
                item_type = self._analyze_type_for_array_item(item, field_name, parent_class)
                item_types.append(item_type)

            type_ref = TypeRef(
                kind=TypeKind.TUPLE,
                name="tuple",
                type_args=item_types,
            )
        else:
            # List type
            self.required_imports.add("list")
            if node.items:
                if isinstance(node.items, list):
                    # Variable length tuple -> use super type
                    if self.config.use_array_of_super_type_for_variable_length_tuple:
                        # Use first item type for simplicity
                        item_type = self._analyze_type_for_array_item(node.items[0], field_name, parent_class)
                    else:
                        item_type = self._analyze_type_for_array_item(node.items[0], field_name, parent_class)
                else:
                    item_type = self._analyze_type_for_array_item(node.items, field_name, parent_class)
            else:
                item_type = TypeRef(kind=TypeKind.ANY, name="Any")

            type_ref = TypeRef(
                kind=TypeKind.ARRAY,
                name="list",
                type_args=[item_type],
            )

        # Handle default value
        if "default" in node.metadata:
            type_ref.has_default = True
            type_ref.default_value = node.metadata["default"]
        elif not is_required:
            type_ref.is_nullable = True

        return type_ref

    def _analyze_type_for_array_item(
        self,
        node: SchemaNode,
        field_name: str,
        parent_class: str,
    ) -> TypeRef:
        """Analyze a type node for array items.

        For Python: Keep nullable types in unions, will be converted to type alias like NoneOrInt.
        For C#: Keep nullable types in unions, will be converted to T?.
        Also uses simple PascalCase names for inline objects (not parent-prefixed).
        """
        # Handle union types specially
        if isinstance(node, UnionNode):
            # Check if this is a nullable union (T | null)
            null_variants = [v for v in node.variants if isinstance(v, PrimitiveNode) and v.type_name == "null"]
            non_null_variants = [v for v in node.variants if not (isinstance(v, PrimitiveNode) and v.type_name == "null")]

            has_null = len(null_variants) > 0

            if len(non_null_variants) == 1 and has_null:
                # Single non-null type + null
                variant = non_null_variants[0]
                if isinstance(variant, ObjectNode):
                    non_null_type = self._analyze_inline_object_type(variant, field_name, parent_class, True, is_array_item=True)
                else:
                    non_null_type = self._analyze_type(variant, field_name, parent_class, True)

                # Check if this is from type: ["T", "null"] (typeArray) vs oneOf: [...] (explicit)
                # For typeArray: strip null for both Python and C# (matches original codegen.py)
                # For explicit oneOf: Python creates type alias (NoneOrInt), C# creates T?
                is_type_array = node.union_type == "typeArray"

                if is_type_array:
                    # Strip null for type arrays in both Python and C#
                    non_null_type.is_nullable = False
                    return non_null_type
                else:
                    # Create a union type with None/null
                    null_type = TypeRef(kind=TypeKind.PRIMITIVE, name="null")
                    type_ref = TypeRef(
                        kind=TypeKind.UNION,
                        name="union",
                        type_args=[non_null_type, null_type],
                        is_nullable=False,  # The union itself handles nullability
                    )
                    return type_ref
            elif len(non_null_variants) > 1:
                # Multiple non-null types - create union
                types = [self._analyze_type(v, field_name, parent_class, True) for v in non_null_variants]
                # Add null if present
                if has_null:
                    types.append(TypeRef(kind=TypeKind.PRIMITIVE, name="null"))
                type_ref = TypeRef(
                    kind=TypeKind.UNION,
                    name="union",
                    type_args=types,
                    is_nullable=False,
                )
                return type_ref

        # Handle inline objects with is_array_item=True
        if isinstance(node, ObjectNode):
            result = self._analyze_inline_object_type(node, field_name, parent_class, True, is_array_item=True)
            result.is_nullable = False
            return result

        # For non-union, non-object types, analyze normally but don't make nullable
        result = self._analyze_type(node, field_name, parent_class, True)
        result.is_nullable = False
        return result

    def _analyze_inline_object_type(
        self,
        node: ObjectNode,
        field_name: str,
        parent_class: str,
        is_required: bool,
        is_array_item: bool = False,
    ) -> TypeRef:
        """Analyze an inline object type."""
        # Get the inline class name
        if is_array_item:
            # Match original codegen.py bug: array items use simple PascalCase
            inline_name = self._to_pascal_case(field_name)
        else:
            inline_name = self.name_mapping.inline_class_names.get(
                (parent_class, field_name),
                f"{parent_class}{self._to_pascal_case(field_name)}",
            )

        type_ref = TypeRef(
            kind=TypeKind.CLASS,
            name=inline_name,
        )

        if not is_required:
            type_ref.is_nullable = True

        return type_ref

    def _analyze_union_type(
        self,
        node: UnionNode,
        field_name: str,
        is_required: bool,
    ) -> TypeRef:
        """Analyze a union type."""
        # Check for nullable union (T | null)
        types = []
        is_nullable = False

        for variant in node.variants:
            if isinstance(variant, PrimitiveNode) and variant.type_name == "null":
                is_nullable = True
            else:
                variant_type = self._analyze_type(variant, field_name, "", True)
                types.append(variant_type)

        if len(types) == 1 and is_nullable:
            # Simple nullable type
            result = types[0]
            result.is_nullable = True
            return result

        # Multiple types - create union
        type_ref = TypeRef(
            kind=TypeKind.UNION,
            name="union",
            type_args=types,
            is_nullable=is_nullable,
        )

        # Handle default value
        if "default" in node.metadata:
            type_ref.has_default = True
            type_ref.default_value = node.metadata["default"]
        elif not is_required and not is_nullable:
            type_ref.is_nullable = True

        return type_ref

    def _analyze_root_node(self) -> ClassDef | None:
        """Analyze the root node (if it has properties)."""
        if not isinstance(self.ast.root_node, ObjectNode):
            return None

        class_def = ClassDef(
            name=self.ast.root_name,
            original_name=self.ast.root_name,
        )

        class_def.fields = self._analyze_properties(self.ast.root_node, self.ast.root_name)
        class_def.constructor_fields = [f for f in class_def.fields if not f.is_const]

        # Generate validation code if enabled
        if self.validator:
            class_def.validation_code = self._generate_validation_code(self.ast.root_node, class_def)

        return class_def

    def _collect_inline_classes(self) -> list[ClassDef]:
        """Collect inline classes that need to be generated."""
        inline_classes = []
        processed = set()

        # Process inline objects from root node
        if self.ast.root_node and isinstance(self.ast.root_node, ObjectNode):
            self._collect_inline_from_object(
                self.ast.root_node,
                self.ast.root_name,
                inline_classes,
                processed,
            )

        # Process inline objects from definitions
        for def_node in self.ast.definitions:
            class_name = self.name_mapping.definition_names.get(def_node.original_name, def_node.original_name)
            if isinstance(def_node.body, ObjectNode):
                self._collect_inline_from_object(
                    def_node.body,
                    class_name,
                    inline_classes,
                    processed,
                )
            elif isinstance(def_node.body, AllOfNode) and def_node.body.extension:
                self._collect_inline_from_object(
                    def_node.body.extension,
                    class_name,
                    inline_classes,
                    processed,
                )

        # Sort inline classes by name to match original codegen.py behavior
        inline_classes.sort(key=lambda c: c.name)
        return inline_classes

    def _collect_inline_from_object(
        self,
        obj: ObjectNode,
        parent_name: str,
        inline_classes: list[ClassDef],
        processed: set[str],
    ) -> None:
        """Recursively collect inline classes from an object node."""
        for prop in obj.properties:
            if prop.name in self.config.global_ignore_fields:
                continue

            type_node = prop.type_node
            if type_node is None:
                continue

            # Check for inline object
            if isinstance(type_node, ObjectNode) and type_node.properties:
                inline_name = self._get_inline_class_name(parent_name, prop.name)
                if inline_name not in processed:
                    processed.add(inline_name)
                    class_def = ClassDef(
                        name=inline_name,
                        original_name=f"{parent_name}.{prop.name}",
                    )
                    class_def.fields = self._analyze_properties(type_node, inline_name)
                    class_def.constructor_fields = [f for f in class_def.fields if not f.is_const]
                    inline_classes.append(class_def)

                    # Recursively process nested inline objects
                    self._collect_inline_from_object(type_node, inline_name, inline_classes, processed)

            # Check for array of inline objects
            elif isinstance(type_node, ArrayNode):
                items = type_node.items
                if isinstance(items, ObjectNode) and items.properties:
                    # Use is_array_item=True to match original codegen.py bug
                    inline_name = self._get_inline_class_name(parent_name, prop.name, is_array_item=True)

                    # Match original codegen.py behavior: last occurrence wins (overwrites)
                    # Remove existing class with same name if present
                    inline_classes[:] = [c for c in inline_classes if c.name != inline_name]
                    processed.discard(inline_name)

                    processed.add(inline_name)
                    class_def = ClassDef(
                        name=inline_name,
                        original_name=f"{parent_name}.{prop.name}",
                    )
                    class_def.fields = self._analyze_properties(items, inline_name)
                    class_def.constructor_fields = [f for f in class_def.fields if not f.is_const]
                    inline_classes.append(class_def)

                    # Recursively process
                    self._collect_inline_from_object(items, inline_name, inline_classes, processed)

    def _get_inline_class_name(self, parent_name: str, field_name: str, is_array_item: bool = False) -> str:
        """Get the inline class name for a field.

        Args:
            parent_name: The parent class name
            field_name: The field name
            is_array_item: If True, use simple PascalCase name to match original codegen.py bug
                          where array item inline classes aren't tracked in the mapping

        Note: The original codegen.py has a bug where the elif for arrays is at the wrong
        indentation level, so array item inline classes never get added to the mapping.
        They fall back to simple PascalCase names, causing collisions.
        """
        if is_array_item:
            # Match original codegen.py bug: array items use simple PascalCase, not parent-prefixed
            return self._to_pascal_case(field_name)

        key = (parent_name, field_name)
        if key in self.name_mapping.inline_class_names:
            return self.name_mapping.inline_class_names[key]
        return f"{parent_name}{self._to_pascal_case(field_name)}"

    def _register_external_import(self, resolved: ResolvedRef) -> None:
        """Register an import for an external $ref."""
        if not self.config.external_ref_base_module:
            return

        # Convert schema path to module path
        path = resolved.external_path.lstrip("/")
        module_path = path.replace("/", ".").replace("_schema", "_dataclass")
        full_module = f"{self.config.external_ref_base_module}.{module_path}"

        self.python_imports.add((full_module, resolved.target_name))

    def _build_imports(self) -> list[ImportDef]:
        """Build the list of required imports."""
        imports = []

        # This will be populated by backends based on what's needed
        return imports

    def _generate_validation_code(self, obj: ObjectNode, class_def: ClassDef) -> list[str]:
        """Generate validation code for a class."""
        if not self.validator:
            return []

        validation_lines = []
        required_fields = obj.required

        for prop in obj.properties:
            if prop.name in self.config.global_ignore_fields:
                continue

            is_required = prop.name in required_fields

            # Get field info in format validator expects
            field_info = self._property_to_validator_info(prop)

            # Get type string
            field_type = ""
            if prop.type_node:
                type_ref = self._analyze_type(prop.type_node, prop.name, class_def.name, is_required)
                # Simple type string for validation
                if type_ref.kind == TypeKind.PRIMITIVE:
                    field_type = type_ref.name
                elif type_ref.kind == TypeKind.ARRAY:
                    field_type = "list"
                elif type_ref.kind == TypeKind.CLASS:
                    field_type = type_ref.name

            # Generate validation
            field_validations = self.validator.generate_field_validation(prop.name, field_info, field_type, is_required)

            # Track if we need 're' import
            if self.validator.needs_re_import(field_info):
                self.needs_re_import = True

            validation_lines.extend(field_validations)

        return validation_lines

    def _property_to_validator_info(self, prop: PropertyDef) -> dict[str, Any]:
        """Convert a PropertyDef to the format expected by ValidationGenerator."""
        info: dict[str, Any] = {}

        if not prop.type_node:
            return info

        node = prop.type_node

        if isinstance(node, PrimitiveNode):
            info["type"] = node.type_name
            if node.min_length is not None:
                info["minLength"] = node.min_length
            if node.max_length is not None:
                info["maxLength"] = node.max_length
            if node.pattern is not None:
                info["pattern"] = node.pattern
            if node.minimum is not None:
                info["minimum"] = node.minimum
            if node.maximum is not None:
                info["maximum"] = node.maximum
            if node.exclusive_minimum is not None:
                info["exclusiveMinimum"] = node.exclusive_minimum
            if node.exclusive_maximum is not None:
                info["exclusiveMaximum"] = node.exclusive_maximum
            if node.multiple_of is not None:
                info["multipleOf"] = node.multiple_of

        elif isinstance(node, ArrayNode):
            info["type"] = "array"
            if node.min_items is not None:
                info["minItems"] = node.min_items
            if node.max_items is not None:
                info["maxItems"] = node.max_items
            if node.items:
                if isinstance(node.items, RefNode):
                    info["items"] = {"$ref": node.items.ref_path}

        elif isinstance(node, RefNode):
            info["$ref"] = node.ref_path

        elif isinstance(node, EnumNode):
            info["enum"] = node.values

        elif isinstance(node, ConstNode):
            info["const"] = node.value

        return info

    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        return self.name_resolver._to_pascal_case(text)

    def _to_enum_member_name(self, value: str) -> str:
        """Convert a value to an enum member name."""
        if self.language == "python":
            return value.upper()
        else:
            return self._to_pascal_case(value)
