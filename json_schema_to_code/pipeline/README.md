# Pipeline-based JSON Schema to Code Generator

This module provides a clean, multi-phase architecture for generating code from JSON schemas.

## Architecture

The pipeline has three phases:

1. **Phase 1 - Parser** (`schema_ast/`): Parse JSON Schema into an AST
2. **Phase 2 - Analyzer** (`analyzer/`): Resolve references and build IR (Intermediate Representation)
3. **Phase 3 - Backends** (`backends/`): Generate language-specific code

## Usage

```python
from json_schema_to_code.pipeline import PipelineGenerator
from json_schema_to_code.pipeline.config import CodeGeneratorConfig

config = CodeGeneratorConfig()
generator = PipelineGenerator("MyClass", schema, config, "python")
code = generator.generate()
```

Or via CLI with the `--use-pipeline` flag:

```bash
json_schema_to_code schema.json output.py -l python --use-pipeline
```

## Features

- Python dataclass generation with dataclasses-json
- C# class generation with Newtonsoft.Json
- Inheritance via allOf
- Enum support with custom member names
- Inline object promotion to classes
- Validation code generation
- Union types (oneOf/anyOf)
- Const and default values

## Known Differences from Original codegen.py

1. **Inline class naming**: The pipeline creates separate classes for each inline object, while the original may deduplicate similar structures.

2. **Class ordering**: Minor differences in class generation order for inline objects.

Both produce valid, equivalent code for all tested schemas.
