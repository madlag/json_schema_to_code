"""
Python AST-based code generation backend.

Generates Python dataclass code from IR using the built-in ast module.
"""

from __future__ import annotations

import ast
import collections
import dataclasses
from typing import Any

from json_schema_to_code.pipeline.config import ClassDefaultStrategy

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

    _OPTIONAL_FIELD_HELPER_BODY = """\
def optional_field_in_json(*args, default=None, **kwargs):
    existing_metadata = kwargs.pop("metadata", {})
    if default is None or isinstance(default, bool):
        exclude_fn = lambda x, d=default: x is d
    else:
        exclude_fn = lambda x, d=default: x == d
    kwargs["metadata"] = {**existing_metadata, **config(exclude=exclude_fn)}
    return field(*args, default=default, **kwargs)
"""

    def __init__(self, config: CodeGeneratorConfig):
        super().__init__(config)
        self.python_imports: set[tuple[str, str]] = set()
        self.needs_re_import = False
        self.type_aliases: set[str] = set()
        self.needs_optional_field_helper = False
        # The classes this IR defines, by name: an absent class-typed field defaults to
        # an empty instance only when that instance can actually be built (see
        # _empty_constructible), which only the class definitions can tell.
        self.classes_by_name: dict[str, ClassDef] = {}
        self._current_class_name: str = ""
        self._constructible: dict[str, bool] = {}

    def generate(self, ir: IR) -> str:
        """Generate Python code from IR using AST."""
        # Reset import tracking
        self.python_imports = set()
        self.needs_re_import = False
        self.type_aliases = set()
        self.needs_optional_field_helper = False
        self.classes_by_name = {c.name: c for c in ir.classes}
        self._constructible = {}

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

        # Inject optional_field_in_json helper if used
        if self.needs_optional_field_helper:
            module = self.config.optional_field_helper_module
            if module == "":
                helper_nodes = ast.parse(self._OPTIONAL_FIELD_HELPER_BODY).body
                body.extend(helper_nodes)
            # import case handled in _generate_imports via python_imports

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
        """Import statements: `__future__` first (Python insists), then modules alphabetically.

        Grouping into stdlib / third-party / first-party is ruff's job (the isort pass
        FormatterConfig.sort_imports turns on): which modules are first-party depends on
        the project the file lands in, so any grouping done here would be wrong for it.
        """
        names_by_module: dict[str, set[str]] = collections.defaultdict(set)
        for module, name in self.python_imports:
            names_by_module[module].add(name)

        entries: list[tuple[str, ast.stmt]] = [
            (module, ast.ImportFrom(module=module, names=[ast.alias(name=n, asname=None) for n in sorted(names)], level=0)) for module, names in names_by_module.items()
        ]
        if self.needs_re_import:
            entries.append(("re", ast.Import(names=[ast.alias(name="re", asname=None)])))
        entries.sort(key=lambda entry: (entry[0] != "__future__", entry[0]))
        return [node for _, node in entries]

    def _generate_class(self, class_def: ClassDef) -> ast.ClassDef | None:
        """Generate a class definition as AST node."""
        if class_def.is_enum:
            return self._generate_enum_class(class_def)

        # Build decorator list.
        # Polymorphic bases are decorated too: a subclass's @dataclass only picks
        # up inherited fields when the base is itself a dataclass, so an
        # undecorated ABC base silently drops every shared field from the
        # children's __init__/to_dict.
        decorators = [
            ast.Name(id="dataclass_json", ctx=ast.Load()),
            ast.Call(
                func=ast.Name(id="dataclass", ctx=ast.Load()),
                args=[],
                keywords=[ast.keyword(arg="kw_only", value=ast.Constant(value=True))],
            ),
        ]

        # Build bases. A concrete base wins over ABC: being marked abstract via
        # ABC is orthogonal to actually inheriting a base's fields, and a class
        # can be both a polymorphic base (has subclasses) and a child of another
        # base (e.g. a middle class in an allOf chain).
        bases = []
        if class_def.base_class:
            bases.append(ast.Name(id=class_def.base_class, ctx=ast.Load()))
        elif class_def.subclasses:
            bases.append(ast.Name(id="ABC", ctx=ast.Load()))
        for extra_base in class_def.extra_base_classes:
            bases.append(ast.Name(id=extra_base, ctx=ast.Load()))

        # Build class body
        body: list[ast.stmt] = []

        # Order fields: required first, then with defaults
        ordered_fields = self._order_fields(class_def.fields)

        self._current_class_name = class_def.name
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

        value, widen_to_none = self._field_default(field)
        if field.omit_when_default and value is None:
            raise ValueError(f"x-omit-when-default on {field.name!r}: the field is required and declares no default, so there is nothing to omit it against.")

        # The annotation follows the default: a None default on a non-nullable class
        # reference reads `X | None`. The IR itself is left as the analyzer built it.
        type_ref = dataclasses.replace(field.type_ref, is_nullable=True) if widen_to_none else field.type_ref
        type_str = self.translate_type(type_ref)

        # Build type annotation
        try:
            type_annotation = ast.parse(type_str, mode="eval").body
        except SyntaxError:
            # Fallback to string annotation
            type_annotation = ast.Constant(value=type_str)

        return ast.AnnAssign(
            target=ast.Name(id=field.name, ctx=ast.Store()),
            annotation=type_annotation,
            value=value,
            simple=1,
        )

    def _field_has_default(self, field: FieldDef) -> bool:
        """Whether the generated declaration carries a default.

        Every non-required field gets one -- None, an empty instance or an empty
        container -- and a required one only when the schema declares it or the type
        admits null. This is the single predicate behind field ordering, empty
        constructibility and the default expression itself.
        """
        type_ref = field.type_ref
        return field.has_default or not field.is_required or (type_ref is not None and (type_ref.has_default or type_ref.is_nullable))

    def _excludes_default(self, field: FieldDef) -> bool:
        """Whether the field is left out of the JSON while it holds its default."""
        return self.config.exclude_default_value_from_json or field.omit_when_default

    def _field_default(self, field: FieldDef) -> tuple[ast.expr | None, bool]:
        """The field's default expression, and whether the annotation must widen to `| None`.

        Widening happens when an absent class-typed field cannot get an empty instance
        and falls back to None while the analyzer marked the type non-nullable.
        """
        type_ref = field.type_ref
        exclude = self._excludes_default(field)

        if field.has_default or type_ref.has_default:
            value = field.default_value if field.has_default else type_ref.default_value
            if type_ref.kind == TypeKind.CLASS and (value is None or isinstance(value, dict)):
                return self._class_default(field, value, exclude)
            return self._format_default_expr(value, type_ref, exclude), False

        if not field.is_required and type_ref.kind == TypeKind.CLASS:
            return self._class_default(field, None, exclude)

        if type_ref.is_nullable:
            return self._format_default_expr(None, type_ref, exclude), False

        return None, False

    def _class_default(self, field: FieldDef, value: dict | None, exclude: bool) -> tuple[ast.expr, bool]:
        """Default for a field typed as a class.

        A dict default is built through `from_dict`, so the field holds an instance and
        not the raw dict. A nullable field defaults to None. An enum with no value
        defaults to None too (`E()` needs a value), widening the annotation. For any
        other class the strategy decides (`ClassDefaultStrategy`): SCHEMA keeps the
        schema's type and emits `default_factory=lambda: X()` — construction raises when
        `X` needs arguments, as the schema implies; CONSTRUCTIBLE widens such a field to
        `X | None = None` so the parent can always be built.
        """
        type_ref = field.type_ref
        class_name = type_ref.name.strip('"')
        if isinstance(value, dict):
            return self._factory_default(f"{class_name}.from_dict({value!r})", exclude), False
        if type_ref.is_nullable:
            return self._format_default_expr(None, type_ref, exclude), False
        constructible_strategy = self.config.class_default_strategy == ClassDefaultStrategy.CONSTRUCTIBLE
        recurses = self._reaches_through_factories(class_name, self._current_class_name)
        if recurses and not constructible_strategy:
            # A None is never introduced silently: a factory that would build the class
            # being generated again can only mean the schema meant nullable.
            raise ValueError(
                f"{self._current_class_name}.{field.name}: a non-nullable optional reference to "
                f"{class_name!r} would build {self._current_class_name!r} again through its "
                f"default factory. Declare the property nullable in the schema "
                f'(`"type": [..., "null"]` / `oneOf` with null), or set '
                f"class_default_strategy=constructible to widen it to None."
            )
        widen = self._is_enum(class_name) or (constructible_strategy and (recurses or not self._empty_constructible(class_name)))
        if widen:
            return self._format_default_expr(None, type_ref, exclude), True
        return self._factory_default(f"{class_name}()", exclude), False

    def _is_enum(self, class_name: str) -> bool:
        class_def = self.classes_by_name.get(class_name)
        return class_def is not None and class_def.is_enum

    def _reaches_through_factories(self, from_class: str, to_class: str, seen: frozenset[str] = frozenset()) -> bool:
        """Whether `from_class()` would build a `to_class()` through empty-instance factories.

        A non-required, non-nullable, non-enum class field with no default gets
        `default_factory=lambda: X()`. If the class being generated is reachable that
        way from a field's own target, the field's factory could never terminate
        (`Node()` building its own `parent: Node`), Under the SCHEMA strategy that is an error naming
        the schema fix (declare it nullable); CONSTRUCTIBLE widens it to None. A
        field that merely points *into* a cycle from outside keeps its factory.
        """
        if from_class == to_class:
            return True
        if from_class in seen:
            return False
        class_def = self.classes_by_name.get(from_class)
        if class_def is None or class_def.is_enum:
            return False
        for f in self._effective_fields(class_def).values():
            ref = f.type_ref
            if (
                ref is not None
                and ref.kind == TypeKind.CLASS
                and not f.is_required
                and not ref.is_nullable
                and not f.has_default
                and not self._is_enum(ref.name.strip('"'))
                and self._reaches_through_factories(ref.name.strip('"'), to_class, seen | {from_class})
            ):
                return True
        return False

    def _factory_default(self, instance: str, exclude: bool) -> ast.expr:
        """`field(default_factory=lambda: <instance>)`; when excluded from JSON, a field still
        equal to a freshly built instance is omitted (so an all-default sub-object is).

        dataclasses_json hands the exclude predicate the field's already-serialized value,
        so the fresh instance is compared in its dict form.
        """
        self.python_imports.add(("dataclasses", "field"))
        if exclude:
            self.python_imports.add(("dataclasses_json", "config"))
            return self._parse_expr(f"field(default_factory=lambda: {instance}, metadata=config(exclude=lambda x: x == {instance}.to_dict()))")
        return self._parse_expr(f"field(default_factory=lambda: {instance})")

    def _empty_constructible(self, class_name: str) -> bool:
        """Whether `Name()` succeeds: every field, inherited ones included, has a default.

        Enums never do. A class this IR does not define (an external $ref) is taken to,
        since nothing here can tell otherwise.
        """
        if class_name not in self._constructible:
            class_def = self.classes_by_name.get(class_name)
            if class_def is None:
                self._constructible[class_name] = True
            else:
                self._constructible[class_name] = not class_def.is_enum and all(self._field_has_default(f) for f in self._effective_fields(class_def).values())
        return self._constructible[class_name]

    def _effective_fields(self, class_def: ClassDef) -> dict[str, FieldDef]:
        """The fields `__init__` takes: inherited first, own fields overriding by name.

        Bases outside this IR contribute nothing -- their fields are unknown here.
        """
        fields: dict[str, FieldDef] = {}
        for base_name in [class_def.base_class, *class_def.extra_base_classes]:
            base = self.classes_by_name.get(base_name) if base_name else None
            if base is not None:
                fields.update(self._effective_fields(base))
        fields.update({f.name: f for f in class_def.fields})
        return fields

    def _emit_helper_call(self, default_repr: str) -> ast.expr:
        """Emit optional_field_in_json(default=X) and mark helper as needed."""
        self.python_imports.add(("dataclasses", "field"))
        self.python_imports.add(("dataclasses_json", "config"))
        self.needs_optional_field_helper = True
        if self.config.optional_field_helper_module:
            self.python_imports.add((self.config.optional_field_helper_module, "optional_field_in_json"))
        return self._parse_expr(f"optional_field_in_json(default={default_repr})")

    def _format_default_expr(self, value: Any, type_ref: TypeRef | None, exclude: bool) -> ast.expr:
        """Format a default value as an AST expression.

        With `exclude`, the field is left out of the JSON while it still equals the
        default -- through the project's helper when one is configured, inline otherwise.
        """
        use_helper = exclude and self.config.optional_field_helper_module is not None

        if value is None:
            if use_helper:
                return self._emit_helper_call("None")
            if exclude:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default=None, metadata=config(exclude=lambda x: x is None))")
            return ast.Constant(value=None)

        if isinstance(value, bool):
            if use_helper:
                return self._emit_helper_call("True" if value else "False")
            if exclude:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                result = "True" if value else "False"
                return self._parse_expr(f"field(default={result}, metadata=config(exclude=lambda x: x is {result}))")
            return ast.Constant(value=value)

        if isinstance(value, str):
            if use_helper:
                escaped = value.replace('"', '\\"')
                return self._emit_helper_call(f'"{escaped}"')
            if exclude:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                escaped = value.replace('"', '\\"')
                return self._parse_expr(f'field(default="{escaped}", metadata=config(exclude=lambda x: x == "{escaped}"))')
            return ast.Constant(value=value)

        if isinstance(value, (int, float)):
            if use_helper:
                return self._emit_helper_call(repr(value))
            if exclude:
                self.python_imports.add(("dataclasses", "field"))
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr(f"field(default={value}, metadata=config(exclude=lambda x: x == {value}))")
            return ast.Constant(value=value)

        if isinstance(value, list):
            return self._format_list_default_expr(value, exclude)

        if isinstance(value, dict):
            return self._format_dict_default_expr(value, exclude)

        return ast.Constant(value=value)

    def _format_list_default_expr(self, value: list, exclude: bool) -> ast.expr:
        """Format a list default value as AST expression."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if exclude:
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default_factory=list, metadata=config(exclude=lambda x: len(x) == 0))")
            return self._parse_expr("field(default_factory=list)")

        # Non-empty list
        items = [repr(item) for item in value]
        content = "[" + ", ".join(items) + "]"

        if exclude:
            self.python_imports.add(("dataclasses_json", "config"))
            return self._parse_expr(f"field(default_factory=lambda: {content}, metadata=config(exclude=lambda x: x == {content}))")
        return self._parse_expr(f"field(default_factory=lambda: {content})")

    def _format_dict_default_expr(self, value: dict, exclude: bool) -> ast.expr:
        """Format a dict default value as AST expression."""
        self.python_imports.add(("dataclasses", "field"))

        if len(value) == 0:
            if exclude:
                self.python_imports.add(("dataclasses_json", "config"))
                return self._parse_expr("field(default_factory=dict, metadata=config(exclude=lambda x: len(x) == 0))")
            return self._parse_expr("field(default_factory=dict)")

        # Non-empty dict
        items = [f"{repr(k)}: {repr(v)}" for k, v in value.items()]
        content = "{" + ", ".join(items) + "}"

        if exclude:
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
        # An explicit x-python-type wins over anything inferred from the schema:
        # it is how a schema maps a shape onto a type the generator must not
        # own (a hand-written class, a plain dict for a foreign wire payload...).
        override = type_ref.type_overrides.get("python")
        if override:
            for module, name in (("typing", "Any"), ("typing", "Literal")):
                if name in override:
                    self.python_imports.add((module, name))
            return override

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

        if type_ref.kind == TypeKind.DICT:
            if len(type_ref.type_args) == 2:
                key_type = self.translate_type(type_ref.type_args[0])
                value_type = self.translate_type(type_ref.type_args[1])
                return f"dict[{key_type}, {value_type}]"
            return "dict"

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
        """Fields without a default first, then the rest, each group in schema order."""
        return [f for f in fields if not self._field_has_default(f)] + [f for f in fields if self._field_has_default(f)]

    def _post_process_code(self, code: str, generation_comment: str) -> str:
        """Post-process the generated code for formatting."""
        # Strip placeholder pass statements (used for blank lines between imports)
        lines = code.split("\n")
        stripped = [line for i, line in enumerate(lines) if not (line.strip() == "pass" and i > 0 and not lines[i - 1].strip().startswith("class"))]
        code = "\n".join(stripped)

        # Prepend generation comment (ruff will handle all PEP 8 spacing)
        if generation_comment:
            code = generation_comment + "\n\n" + code

        return code
