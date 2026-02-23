# AGENTS.md -- json_schema_to_code context for AI agents

## Project overview

**json_schema_to_code** generates strongly-typed classes from JSON Schema definitions for Python and C#. It uses a five-phase AST-based pipeline: parse, analyze, generate AST, serialize, format/merge.

- **Stack**: Python 3.12+, Click (CLI), ruff (formatting), tree-sitter (C# merge parsing)
- **Entry point**: `json_schema_to_code` CLI command (defined in `pyproject.toml`)

## Key paths

| Area | Path |
|------|------|
| CLI entry point | `json_schema_to_code/json_schema_to_code.py` |
| Pipeline config | `json_schema_to_code/pipeline/config.py` |
| Main generator | `json_schema_to_code/pipeline/generator.py` |
| Schema AST nodes | `json_schema_to_code/pipeline/schema_ast/nodes.py` |
| Schema parser | `json_schema_to_code/pipeline/schema_ast/parser.py` |
| IR nodes | `json_schema_to_code/pipeline/analyzer/ir_nodes.py` |
| Schema analyzer | `json_schema_to_code/pipeline/analyzer/analyzer.py` |
| Reference resolver | `json_schema_to_code/pipeline/analyzer/reference_resolver.py` |
| Name resolver | `json_schema_to_code/pipeline/analyzer/name_resolver.py` |
| Backend base class | `json_schema_to_code/pipeline/ast_backends/base.py` |
| Python backend | `json_schema_to_code/pipeline/ast_backends/python_ast_backend.py` |
| C# backend | `json_schema_to_code/pipeline/ast_backends/csharp_ast_backend.py` |
| C# serializer | `json_schema_to_code/pipeline/ast_backends/csharp_serializer.py` |
| Merger base | `json_schema_to_code/pipeline/merger/base.py` |
| Python merger | `json_schema_to_code/pipeline/merger/python_merger.py` |
| C# merger | `json_schema_to_code/pipeline/merger/csharp_merger.py` |
| Atomic writer | `json_schema_to_code/pipeline/merger/atomic_writer.py` |
| Ruff formatter | `json_schema_to_code/pipeline/formatters/ruff_formatter.py` |
| Tests | `json_schema_to_code/tests/` |
| Test data | `json_schema_to_code/tests/test_data/` |

## CLI usage

```bash
json_schema_to_code <schema.json> <output_file> [options]

# Options:
#   --name, -n        Root class name (default: schema filename stem)
#   --config, -c      JSON config file path
#   --language, -l    Target language: "cs" (default) or "python"
#   --add-validation  Add runtime validation code
#   --merge-strategy  "error" | "merge" | "delete"
```

## Pipeline architecture

### Phase 1: Schema Parsing (`schema_ast/parser.py`)

`SchemaParser.parse()` converts raw JSON Schema dict into a `SchemaAST` tree. No references are resolved at this stage.

**Schema AST node types** (in `schema_ast/nodes.py`):

| Node | Description |
|------|-------------|
| `PrimitiveNode` | `string`, `integer`, `number`, `boolean`, `null`, `object` |
| `ConstNode` | Const literal values |
| `EnumNode` | Enum types (with optional `x-enum-members`) |
| `RefNode` | Unresolved `$ref` references |
| `ArrayNode` | Array types (single item or tuple items) |
| `ObjectNode` | Object types with `PropertyDef` list |
| `UnionNode` | `oneOf` / `anyOf` unions |
| `AllOfNode` | Inheritance via `allOf` (base_ref + extension) |
| `DefinitionNode` | Schema definition entry (`$defs` / `definitions`) |

### Phase 2: Analysis (`analyzer/analyzer.py`)

`SchemaAnalyzer.analyze()` transforms the Schema AST into an IR (Intermediate Representation). Resolves `$ref` references, builds inheritance graph, handles discriminated unions.

**IR node types** (in `analyzer/ir_nodes.py`):

| IR Node | Description |
|---------|-------------|
| `IR` | Root container: classes, enums, type aliases, imports |
| `ClassDef` | Class with fields, base_class, subclasses, discriminator_property |
| `FieldDef` | Field with name, type_ref, is_required, default_value, is_const |
| `EnumDef` | Enum with members (name -> value mapping) |
| `TypeAlias` | Union type alias |
| `TypeRef` | Resolved type reference with kind, name, type_args, nullable |
| `ImportDef` | Import statement |

**`TypeKind` enum values**: `PRIMITIVE`, `CLASS`, `ARRAY`, `TUPLE`, `DICT`, `UNION`, `OPTIONAL`, `ENUM`, `CONST`, `ANY`, `TYPE_ALIAS`

### Phase 3: AST Backend Generation (`ast_backends/`)

`AstBackend.generate(ir)` converts IR to language-native AST. Backends inherit from `AstBackend` and implement:
- `generate(ir: IR) -> str`
- `translate_type(type_ref: TypeRef) -> str`
- `format_default_value(value: Any, type_ref: TypeRef) -> str`

**Backends**: `PythonAstBackend`, `CSharpAstBackend`

### Phase 4: Serialization

- Python: `ast.unparse()` (standard library)
- C#: custom `CSharpSerializer` in `csharp_serializer.py`

### Phase 5: Formatting & Merging

- **Formatting**: `RuffFormatter` for Python (configurable via `FormatterConfig`)
- **Merging**: `PythonAstMerger` / `CSharpAstMerger` preserve custom code in existing files
- **Atomic writes**: `AtomicWriter` writes to temp file then renames

## Configuration

`CodeGeneratorConfig` (in `pipeline/config.py`), loaded from JSON via `--config`:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ignore_classes` | `list[str]` | `[]` | Classes to skip |
| `global_ignore_fields` | `list[str]` | `[]` | Fields to exclude globally |
| `order_classes` | `list[str]` | `[]` | Class generation order |
| `ignoreSubClassOverrides` | `bool` | `false` | Skip redundant subclass field overrides (keeps const overrides) |
| `drop_min_max_items` | `bool` | `false` | Ignore array length constraints |
| `use_array_of_super_type_for_variable_length_tuple` | `bool` | `true` | Use arrays for variable-length tuples |
| `use_tuples` | `bool` | `true` | Generate tuple types |
| `use_inline_unions` | `bool` | `false` | Inline unions vs type aliases |
| `add_generation_comment` | `bool` | `true` | Comment at top of file |
| `quoted_types_for_python` | `list[str]` | `[]` | Types to quote for forward references |
| `use_future_annotations` | `bool` | `true` | Add `from __future__ import annotations` |
| `exclude_default_value_from_json` | `bool` | `false` | Exclude defaults from JSON serialization |
| `add_validation` | `bool` | `false` | Add runtime validation |
| `external_ref_base_module` | `str` | `""` | Base module for external `$ref` imports (Python) |
| `external_ref_schema_to_module` | `dict[str,str]` | `{}` | Schema path -> module mapping |
| `csharp_namespace` | `str` | `""` | C# namespace |
| `csharp_additional_usings` | `list[str]` | `[]` | Extra C# using statements |
| `schema_base_path` | `str` | `""` | Base path for resolving external `$ref` schemas from disk |

**Output config** (nested under `output` in JSON):

| Option | Values | Default |
|--------|--------|---------|
| `mode` | `error_if_exists`, `overwrite`, `merge` | `merge` |
| `merge_strategy` | `error`, `merge`, `delete` | `error` |

**Formatter config** (nested under `formatter`):

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable ruff formatting |
| `line_length` | `100` | Line length |
| `target_version` | `""` | Python target (e.g. `py313`) |

## Code merging

When `output.mode = "merge"`, the generator preserves custom code from the existing file. The merger extracts and reinserts:

- Custom imports
- Module-level constants
- Custom classes (not in generated schema)
- Custom class methods
- Custom class attributes
- `__post_init__` bodies (Python)
- Raw code sections (marked with `// CUSTOM CODE` or `# CUSTOM CODE`)
- Docstrings

**Merge strategy** controls what happens with value members in the existing file that are not in the new generated code:
- `error`: Raise error (safest)
- `merge`: Keep extra members
- `delete`: Remove extra members

**`# jstc-no-merge`**: Add this comment to a line in existing code to prevent merging on that line.

## Schema extensions

| Extension | Where | Description |
|-----------|-------|-------------|
| `x-enum-members` | Enum definition | Maps enum values to custom Python member names |
| `x-ref-class-name` | `$ref` | Override the resolved class name |
| `x-csharp-implements` | Object | C# interface to implement |
| `x-csharp-properties` | Object | C# interface property mappings |

## Inheritance

`allOf` with a `$ref` + extension object maps to class inheritance:
- The `$ref` becomes the base class
- Extension properties become subclass fields
- Discriminator is auto-detected from const fields (typically `type`)
- C#: `JsonSubTypes` attributes for polymorphic deserialization
- Python: `ABC` for abstract base classes

## Testing

**Framework**: pytest

**Test locations**:
- `json_schema_to_code/tests/` -- main test files
- `json_schema_to_code/tests/v3/` -- v3 pipeline-specific tests
- `json_schema_to_code/tests/test_data/` -- test schemas, reference outputs, merge fixtures

**Key test files**:

| File | Tests |
|------|-------|
| `test_functional.py` | Schema-to-code generation for various schemas |
| `test_merge.py` | Code merging (output modes, merge strategies) |
| `test_pipeline_integration.py` | Full pipeline integration |
| `test_code_merge_roundtrip.py` | Merge roundtrip (generate -> merge -> verify) |
| `test_external_base_class_imports.py` | External `$ref` import resolution |
| `test_csharp_ast_roundtrip.py` | C# AST parsing roundtrip |
| `test_validation_rules.py` | Validation rule generation |
| `test_cli_utils.py` | CLI utility functions |

**Running tests**:
```bash
python -m pytest json_schema_to_code/tests/ -v
```

**Test data patterns**:
- `test_data/test_cases/<case>/` -- schema + reference outputs (`.py`, `.cs`)
- `test_data/code_merge/<case>/` -- schema + existing dataclass files for merge testing
- `test_data/functional/*.json` -- parameterized functional test data
- `test_data/pipeline/` -- pipeline-specific test schemas

## Python API

```python
from json_schema_to_code import PipelineGenerator, CodeGeneratorConfig

config = CodeGeneratorConfig()
generator = PipelineGenerator("MySchema", schema_dict, config, "python")

# Generate code string
code = generator.generate()

# Or generate and write to file (handles merging, formatting, atomic write)
generator.generate_to_file(Path("output.py"))
```

## Name resolution

- Definition names are converted to PascalCase
- Inline objects: `{ParentClass}{FieldName}` in PascalCase
- C# keywords escaped with `@` prefix
- Collision handling via `NameResolver`

## Ruff configuration

The project's `pyproject.toml` configures ruff with `line-length = 200` for the project source itself. Generated code uses `line_length = 100` (from `FormatterConfig`).
