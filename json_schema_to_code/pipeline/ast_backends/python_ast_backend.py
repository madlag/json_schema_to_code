"""
Python AST-based code generation backend.

Generates Python dataclass code from IR using the built-in ast module.
"""

from __future__ import annotations

import ast
import collections
from typing import Any

from ..analyzer.ir_nodes import IR, ClassDef, FieldDef, TypeAlias, TypeKind, TypeRef
from ..config import CodeGeneratorConfig
from .base import AstBackend


class PythonAstBackend(AstBackend):
    """Python code generation backend using AST."""

    FILE_EXTENSION = "py"

    TYPE_MAP = {
        "integer": "int",
        "string": "str",
        "boolean": "bool",
        "number": "float",
        "null": "None",
        "object": "Any",
        "list": "list",
        "dict": "dict",
        "tuple": "tuple",
    }

    def __init__(self, config: CodeGeneratorConfig):
        super().__init__(config)
        self.python_imports: set[tuple[str, str]] = set()
        self.needs_re_import = False
        self.type_aliases: set[str] = set()

    def generate(self, ir: IR) -> str:
        """Generate Python code from IR using AST."""
        # Reset import tracking
        self.python_imports = set()
        self.needs_re_import = False
        self.type_aliases = set()

        # Build the module body
        body: list[ast.stmt] = []

        # Add generation comment as a module docstring if present
        # (We'll add it as a comment later since AST doesn't support comments well)

        # Always include base imports
        self.python_imports.add(("dataclasses", "dataclass"))
        self.python_imports.add(("dataclasses_json", "dataclass_json"))

        # Add future annotations if configured
        if self.config.use_future_annotations:
            self.python_imports.add(("__future__", "annotations"))

        # Check for special imports needed
        self._scan_ir_for_imports(ir)

        # Generate class definitions
        class_nodes = []
        for class_def in ir.classes:
            class_node = self._generate_class(class_def)
            if class_node:
                class_nodes.append(class_node)

        # Separate type aliases
        simple_aliases = []
        forward_aliases = []
        class_names = {c.name for c in ir.classes}

        for alias in ir.type_aliases:
            alias_str = self._format_type_alias(alias)
            has_forward = any(name in alias_str for name in class_names)
            if has_forward:
                forward_aliases.append(alias_str)
            else:
                simple_aliases.append(alias_str)

        for alias_def in self.type_aliases:
            has_forward = any(name in alias_def for name in class_names)
            if has_forward:
                forward_aliases.append(alias_def)
            else:
                simple_aliases.append(alias_def)

        # Assemble imports
        import_nodes = self._generate_imports()
        body.extend(import_nodes)

        # Add simple type aliases before classes
        for alias in sorted(simple_aliases):
            alias_node = self._parse_type_alias(alias)
            if alias_node:
                body.append(alias_node)

        # Add blank line after imports/aliases
        if body:
            body.append(ast.Pass())  # Placeholder for blank line

        # Add class definitions
        body.extend(class_nodes)

        # Add forward reference aliases after classes
        for alias in sorted(forward_aliases):
            alias_node = self._parse_type_alias(alias)
            if alias_node:
                body.append(alias_node)

        # Create module
        module = ast.Module(body=body, type_ignores=[])
        ast.fix_missing_locations(module)

        # Unparse to source code
        code = ast.unparse(module)

        # Post-process: add generation comment and fix formatting
        code = self._post_process_code(code, ir.generation_comment)

        return code

    def _scan_ir_for_imports(self, ir: IR) -> None:
        """Scan IR to determine required imports."""
        # Add imports from IR (e.g., external base classes)
        for import_def in ir.imports:
            for name in import_def.names:
                self.python_imports.add((import_def.module, name))

        for class_def in ir.classes:
            if class_def.subclasses:
                self.python_imports.add(("abc", "ABC"))
            if class_def.is_enum:
                self.python_imports.add(("enum", "Enum"))
            for line in class_def.validation_code:
                if "re.match" in line or "re.fullmatch" in line:
                    self.needs_re_import = True

    def _generate_imports(self) -> list[ast.stmt]:
        """Generate import statements as AST nodes."""
        import_groups: dict[str, set[str]] = collections.defaultdict(set)
        for module, name in self.python_imports:
            import_groups[module].add(name)

        STDLIB_MODULES = {"abc", "collections", "dataclasses", "enum", "typing", "re"}

        stdlib_groups = {m: import_groups[m] for m in import_groups if m in STDLIB_MODULES}
        third_party_groups = {m: import_groups[m] for m in import_groups if m not in STDLIB_MODULES and m != "__future__"}

        nodes: list[ast.stmt] = []

        # __future__ imports first
        if "__future__" in import_groups:
            names = sorted(import_groups["__future__"])
            nodes.append(
                ast.ImportFrom(
                    module="__future__",
                    names=[ast.alias(name=n, asname=None) for n in names],
                    level=0,
                )
            )

        # re module import
        if self.needs_re_import:
            nodes.append(ast.Import(names=[ast.alias(name="re", asname=None)]))

        # Standard library
        for module in sorted(stdlib_groups.keys()):
            names = sorted(stdlib_groups[module])
            nodes.append(
                ast.ImportFrom(
                    module=module,
                    names=[ast.alias(name=n, asname=None) for n in names],
                    level=0,
                )
            )

        # Third party
        for module in sorted(third_party_groups.keys()):
            names = sorted(third_party_groups[module])
            nodes.append(
                ast.ImportFrom(
                    module=module,
                    names=[ast.alias(name=n, asname=None) for n in names],
                    level=0,
                )
            )

        return nodes

    def _generate_class(self, class_def: ClassDef) -> ast.ClassDef | None:
        """Generate a class definition as AST node."""
        if class_def.is_enum:
            return self._generate_enum_class(class_def)

        # Build decorator list
        decorators = []
        if not class_def.subclasses:  # Abstract classes don't get decorators
            decorators.append(ast.Name(id="dataclass_json", ctx=ast.Load()))
            decorators.append(
                ast.Call(
                    func=ast.Name(id="dataclass", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="kw_only", value=ast.Constant(value=True))],
                )
            )

        # Build bases
        bases = []
        if class_def.subclasses:
            bases.append(ast.Name(id="ABC", ctx=ast.Load()))
        elif class_def.base_class:
            bases.append(ast.Name(id=class_def.base_class, ctx=ast.Load()))

        # Build class body
        body: list[ast.stmt] = []

        # Order fields: required first, then with defaults
        ordered_fields = self._order_fields(class_def.fields)

        for field in ordered_fields:
            field_node = self._generate_field(field)
            if field_node:
                body.append(field_node)

        # Add validation method if needed
        if class_def.validation_code:
            validation_method = self._generate_post_init(class_def.validation_code)
            body.append(validation_method)

        # Empty class body
        if not body:
            body.append(ast.Pass())

        return ast.ClassDef(
            name=class_def.name,
            bases=bases,
            keywords=[],
            body=body,
            decorator_list=decorators,
        )

    def _generate_enum_class(self, class_def: ClassDef) -> ast.ClassDef:
        """Generate an enum class definition."""
        if not class_def.enum_def:
            raise ValueError(f"Enum class {class_def.name} has no enum_def")

        # Build bases
        bases = []
        if class_def.enum_def.value_type == "string":
            bases.append(ast.Name(id="str", ctx=ast.Load()))
        elif class_def.enum_def.value_type == "integer":
            bases.append(ast.Name(id="int", ctx=ast.Load()))
        bases.append(ast.Name(id="Enum", ctx=ast.Load()))

        # Build body with enum members
        body: list[ast.stmt] = []
        for member_name, member_value in class_def.enum_def.members.items():
            body.append(
                ast.Assign(
                    targets=[ast.Name(id=member_name, ctx=ast.Store())],
                    value=ast.Constant(value=member_value),
                )
            )

        if not body:
            body.append(ast.Pass())

        return ast.ClassDef(
            name=class_def.name,
            bases=bases,
            keywords=[],
            body=body,
            decorator_list=[],
        )

    def _generate_field(self, field: FieldDef) -> ast.AnnAssign | None:
        """Generate a field definition as annotated assignment."""
        if not field.type_ref:
            return None

        type_str = self.translate_type(field.type_ref)

        # Build type annotation
        try:
            type_annotation = ast.parse(type_str, mode="eval").body
        except SyntaxError:
            # Fallback to string annotation
            type_annotation = ast.Constant(value=type_str)

        # Determine if we need a default value
        value = self._get_field_default(field)

        return ast.AnnAssign(
            target=ast.Name(id=field.name, ctx=ast.Store()),
            annotation=type_annotation,
            value=value,
            simple=1,
        )

    def _get_field_default(self, field: FieldDef) -> ast.expr | None:
        """Get the default value expression for a field."""
        has_explicit_default = field.has_default or (field.type_ref and field.type_ref.has_default)
        is_nullable = field.type_ref and field.type_ref.is_nullable

        if has_explicit_default:
            default_val = field.default_value if field.has_default else field.type_ref.default_value

            # Special case: null default on $ref means auto-initialize with default_factory
            if default_val is None and field.type_ref and field.type_ref.kind == TypeKind.CLASS:
                clean_type = field.type_ref.name.strip('"')
                self.python_imports.add(("dataclasses", "field"))
                return self._parse_expr(f"field(default_factory=lambda: {clean_type}())")

            return self._format_default_expr(default_val, field.type_ref)

        elif not field.is_required and field.type_ref and field.type_ref.kind == TypeKind.CLASS:
            # Optional CLASS types without explicit default
            if is_nullable:
                return self._format_default_expr(None, field.type_ref)
            else:
                clean_type = field.type_ref.name.strip('"')
                self.python_imports.add(("dataclasses", "field"))
                return self._parse_expr(f"field(default_factory=lambda: {clean_type}())")

        elif is_nullable:
            return self._format_default_expr(None, field.type_ref)

        return None

    def _format_default_expr(self, value: Any, type_ref: TypeRef | None) -> ast.expr:
        """Format a default value as an AST expression."""
        if value is None:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default=None, metadata=config(exclude=lambda x: x is None))")
            return ast.Constant(value=None)

        if isinstance(value, bool):
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                result = "True" if value else "False"
                return self._parse_expr(f"field(default={result}, metadata=config(exclude=lambda x: x is {result}))")
            return ast.Constant(value=value)

        if isinstance(value, str):
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                escaped = value.replace('"', '\\"')
                return self._parse_expr(f'field(default="{escaped}", metadata=config(exclude=lambda x: x == "{escaped}"))')
            return ast.Constant(value=value)

        if isinstance(value, (int, float)):
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr(f"field(default={value}, metadata=config(exclude=lambda x: x == {value}))")
            return ast.Constant(value=value)

        if isinstance(value, list):
            return self._format_list_default_expr(value)

        if isinstance(value, dict):
            return self._format_dict_default_expr(value)

        return ast.Constant(value=value)

    def _format_list_default_expr(self, value: list) -> ast.expr:
        """Format a list default value as AST expression."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default_factory=list, metadata=config(exclude=lambda x: len(x) == 0))")
            return self._parse_expr("field(default_factory=list)")

        # Non-empty list
        items = [repr(item) for item in value]
        content = "[" + ", ".join(items) + "]"

        if self.config.exclude_default_value_from_json:
            self.python_imports.add(("dataclasses_json", "config"))
            return self._parse_expr(f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))")
        return self._parse_expr(f"field(default_factory=lambda: {content})")

    def _format_dict_default_expr(self, value: dict) -> ast.expr:
        """Format a dict default value as AST expression."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if self.config.exclude_default_value_from_json:
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default_factory=dict, metadata=config(exclude=lambda x: len(x) == 0))")
            return self._parse_expr("field(default_factory=dict)")

        # Non-empty dict
        items = [f"{repr(k)}: {repr(v)}" for k, v in value.items()]
        content = "{" + ", ".join(items) + "}"

        if self.config.exclude_default_value_from_json:
            self.python_imports.add(("dataclasses_json", "config"))
            return self._parse_expr(f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))")
        return self._parse_expr(f"field(default_factory=lambda: {content})")

    def _generate_post_init(self, validation_code: list[str]) -> ast.FunctionDef:
        """Generate __post_init__ method for validation."""
        body: list[ast.stmt] = []

        # Add docstring
        body.append(ast.Expr(value=ast.Constant(value="Validate the object after initialization.")))

        # Add validation lines
        for line in validation_code:
            try:
                stmt = ast.parse(line, mode="exec").body[0]
                body.append(stmt)
            except SyntaxError:
                # Skip invalid validation lines
                pass

        if len(body) == 1:  # Only docstring
            body.append(ast.Pass())

        return ast.FunctionDef(
            name="__post_init__",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="self", annotation=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def translate_type(self, type_ref: TypeRef) -> str:
        """Translate IR type to Python type string."""
        result = self._translate_type_inner(type_ref)

        # Handle nullability
        if type_ref.is_nullable and not result.endswith(" | None"):
            result = f"{result} | None"

        # Handle quoting
        if type_ref.is_quoted:
            result = f'"{result}"'

        return result

    def _translate_type_inner(self, type_ref: TypeRef) -> str:
        """Inner type translation without nullable handling."""
        if type_ref.kind == TypeKind.PRIMITIVE:
            type_name = self.TYPE_MAP.get(type_ref.name, type_ref.name)
            if type_name == "Any":
                self.python_imports.add(("typing", "Any"))
            return type_name

        if type_ref.kind == TypeKind.CLASS:
            return type_ref.name

        if type_ref.kind == TypeKind.ANY:
            self.python_imports.add(("typing", "Any"))
            return "Any"

        if type_ref.kind == TypeKind.ARRAY:
            if type_ref.type_args:
                item_type = self.translate_type(type_ref.type_args[0])
                return f"list[{item_type}]"
            return "list"

        if type_ref.kind == TypeKind.TUPLE:
            if type_ref.type_args:
                item_types = ", ".join(self.translate_type(t) for t in type_ref.type_args)
                return f"tuple[{item_types}]"
            return "tuple"

        if type_ref.kind == TypeKind.UNION:
            types = [self.translate_type(t) for t in type_ref.type_args]
            sorted_types = sorted(types)
            union_string = " | ".join(sorted_types)

            if self.config.use_inline_unions:
                return union_string

            # Create type alias
            alias_parts = []
            for t in sorted_types:
                clean_t = t.strip('"') if t.startswith('"') else t
                alias_parts.append(self._snake_to_pascal(clean_t.replace(" | ", "Or")))

            type_alias_name = "Or".join(alias_parts)
            self.type_aliases.add(f"{type_alias_name} = {union_string}")
            return type_alias_name

        if type_ref.kind == TypeKind.CONST:
            self.python_imports.add(("typing", "Literal"))
            formatted = self._format_literal_value(type_ref.const_value)
            return f"Literal[{formatted}]"

        if type_ref.kind == TypeKind.ENUM:
            # String enums with values become Literal types
            if type_ref.enum_values and type_ref.name == "string":
                self.python_imports.add(("typing", "Literal"))
                formatted_values = ", ".join(self._format_literal_value(v) for v in type_ref.enum_values)
                return f"Literal[{formatted_values}]"
            # Fallback to base type for enums without values
            return self.TYPE_MAP.get(type_ref.name, type_ref.name)

        return "Any"

    def format_default_value(self, value: Any, type_ref: TypeRef) -> str:
        """Format a default value for Python."""
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _format_literal_value(self, value: Any) -> str:
        """Format a value for Literal type."""
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _format_type_alias(self, alias: TypeAlias) -> str:
        """Format a type alias as Python code."""
        if alias.union_components:
            union_str = " | ".join(sorted(alias.union_components))
            return f"{alias.name} = {union_str}"
        return f"{alias.name} = Any"

    def _parse_type_alias(self, alias_str: str) -> ast.Assign | None:
        """Parse a type alias string into an AST assignment."""
        try:
            module = ast.parse(alias_str, mode="exec")
            if module.body:
                return module.body[0]
        except SyntaxError:
            pass
        return None

    def _parse_expr(self, expr_str: str) -> ast.expr:
        """Parse an expression string into an AST expression."""
        return ast.parse(expr_str, mode="eval").body

    def _order_fields(self, fields: list[FieldDef]) -> list[FieldDef]:
        """Order fields for dataclass compatibility."""
        required_fields = []
        optional_fields = []

        for field in fields:
            has_default = field.has_default
            is_nullable = field.type_ref and field.type_ref.is_nullable
            type_has_default = field.type_ref and field.type_ref.has_default
            is_optional_class = not field.is_required and field.type_ref and field.type_ref.kind == TypeKind.CLASS

            if has_default or is_nullable or type_has_default or is_optional_class:
                optional_fields.append(field)
            else:
                required_fields.append(field)

        return required_fields + optional_fields

    def _post_process_code(self, code: str, generation_comment: str) -> str:
        """Post-process the generated code for formatting."""
        lines = code.split("\n")
        result = []

        # Add generation comment at the top
        if generation_comment:
            result.append(generation_comment)
            result.append("")

        # Process lines
        for i, line in enumerate(lines):
            # Skip placeholder pass statements (used for blank lines)
            if line.strip() == "pass" and i > 0 and not lines[i - 1].strip().startswith("class"):
                result.append("")
                continue

            # Add blank lines before class definitions
            if line.startswith("@dataclass") or line.startswith("class "):
                if result and result[-1].strip() != "":
                    result.append("")

            result.append(line)

        # Ensure file ends with newline
        if result and result[-1] != "":
            result.append("")

        return "\n".join(result)
