# JSON Schema to Code Generator

A Python package that generates strongly-typed classes from JSON Schema definitions. Supports code generation for **Python** and **C#** with full inheritance, polymorphism, and type safety.

## Features

- **Multi-language support**: Generate Python dataclasses and C# classes
- **Full JSON Schema compliance**: Supports definitions, references, inheritance (`allOf`), enums, and complex types
- **Type safety**: Generates strongly-typed code with proper nullable handling
- **Inheritance and polymorphism**: Handles base classes and subclass discrimination
- **Template-based**: Uses Jinja2 templates for customizable code generation
- **Configuration support**: Flexible configuration options for customizing output
- **Command-line interface**: Easy-to-use CLI tool

## Installation

```bash
pip install json_schema_to_code
```

### Dependencies

- Python 3.12+
- Click (CLI interface)

## Quick Start

### Command Line Usage

```bash
# Basic usage - generate C# classes
json_schema_to_code schema.json output.cs

# Generate Python dataclasses
json_schema_to_code schema.json output.py --language python

# Use a configuration file
json_schema_to_code schema.json output.cs --config config.json

# Specify a custom class name
json_schema_to_code schema.json output.cs --name MyRootClass
```

### Command Line Options

- `path`: Input JSON Schema file (required)
- `output`: Output file path (required)
- `--language, -l`: Target language (`cs` or `python`, default: `cs`)
- `--config, -c`: Configuration file path (optional)
- `--name, -n`: Root class name (optional, defaults to schema filename)
- `--add-validation`: Add runtime validation code (optional)

## Configuration

Create a JSON configuration file to customize code generation:

```json
{
  "ignore_classes": ["TempClass", "DebugInfo"],
  "global_ignore_fields": ["_internal", "__debug"],
  "order_classes": ["BaseMessage", "ErrorMessage"],
  "ignoreSubClassOverrides": false,
  "drop_min_max_items": false,
  "use_array_of_super_type_for_variable_length_tuple": true,
  "use_tuples": true,
  "quoted_types_for_python": ["Node", "Tree"]
}
```

### Configuration Options

- **`ignore_classes`**: List of class names to skip during generation
- **`global_ignore_fields`**: Field names to exclude from all classes
- **`order_classes`**: Specify the order of class generation
- **`ignoreSubClassOverrides`**: Skip property overrides in subclasses
- **`drop_min_max_items`**: Ignore array length constraints
- **`use_array_of_super_type_for_variable_length_tuple`**: Use arrays for variable-length tuples
- **`use_tuples`**: Generate tuple types for fixed-length arrays
- **`quoted_types_for_python`**: List of type names to quote in Python type references (e.g., `List["MyType"]` instead of `List[MyType]`) to handle circular type definitions

## Supported JSON Schema Features

### Basic Types
- `string`, `integer`, `number`, `boolean`, `null`
- `array` with typed items
- `object` with properties
- `enum` values

### Advanced Features
- **References**: `$ref` to definitions
- **Inheritance**: `allOf` for class hierarchies
- **Polymorphism**: Automatic subclass discrimination
- **Union types**: Multiple type options (`oneOf`)
- **Const values**: Fixed literal values
- **Optional properties**: Nullable type generation
- **Custom enum member names**: Use `x-enum-members` to specify custom Python enum member names

### Custom Enum Member Names

By default, when generating Python enum classes, the generator uses the enum values directly as member names (e.g., `"N"` becomes `N = "N"`). To use more descriptive member names, you can use the `x-enum-members` extension:

```json
{
  "$defs": {
    "ElementState": {
      "type": "string",
      "enum": ["N", "H", "C"],
      "x-enum-members": {
        "N": "NORMAL",
        "H": "HIDDEN",
        "C": "CORRECT_ANSWER"
      }
    }
  }
}
```

When preprocessing the schema (before passing it to `CodeGenerator`), transform the enum array into a dict mapping member names to values. The generator will then use this dict to create enum classes with custom member names:

```python
class ElementState(str, Enum):
    NORMAL = "N"
    HIDDEN = "H"
    CORRECT_ANSWER = "C"
```

**Note**: The `x-enum-members` extension maps enum values (the keys) to Python enum member names (the values). This requires preprocessing the schema to transform `enum` arrays into dicts before code generation. This feature is currently only supported for Python code generation.

## Output Examples

### Input Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "definitions": {
    "Shape": {
      "type": "object",
      "properties": {
        "type": {"type": "string"}
      },
      "required": ["type"]
    },
    "Circle": {
      "allOf": [
        {"$ref": "#/definitions/Shape"},
        {
          "properties": {
            "type": {"const": "circle"},
            "radius": {"type": "number"}
          },
          "required": ["radius"]
        }
      ]
    }
  }
}
```

### Generated C# Code
```csharp
using System;
using System.Collections.Generic;
using JsonSubTypes;
using Newtonsoft.Json;

[Serializable]
[JsonConverter(typeof(JsonSubtypes), "type")]
[JsonSubtypes.KnownSubType(typeof(Circle), "circle")]
public class Shape
{
    public string type;
    public Shape(string type)
    {
        this.type = type;
    }
}

[Serializable]
public class Circle : Shape
{
    public float radius;
    public Circle(float radius): base("circle")
    {
        this.radius = radius;
    }
}
```

### Generated Python Code
```python
from dataclasses import dataclass
from typing import Literal
from dataclasses_json import dataclass_json
from abc import ABC

@dataclass_json
@dataclass(kw_only=True)
class Shape(ABC):
    pass

@dataclass_json
@dataclass(kw_only=True)
class Circle(Shape):
    type: Literal["circle"] = "circle"
    radius: float
```

## Python API Usage

```python
from json_schema_to_code import PipelineGenerator, CodeGeneratorConfig
import json

# Load schema
with open('schema.json') as f:
    schema = json.load(f)

# Create configuration
config = CodeGeneratorConfig()
config.ignore_classes = ['TempClass']

# Generate code
generator = PipelineGenerator('MySchema', schema, config, 'python')
code = generator.generate()

# Save to file
with open('output.py', 'w') as f:
    f.write(code)
```

## Language-Specific Features

### Python Output
- Uses `@dataclass` with `dataclasses_json` for JSON serialization
- Supports union types with `|` syntax (Python 3.10+)
- Generates `Literal` types for const values
- Uses `ABC` for abstract base classes

### C# Output
- Includes `[Serializable]` attributes
- Uses `JsonSubTypes` for polymorphic serialization
- Generates proper constructors with base class calls
- Supports nullable reference types

## Architecture

The generator uses an AST-based pipeline for code generation:

1. **Schema Parser**: Parses JSON Schema into an AST
2. **Analyzer**: Resolves references and builds an intermediate representation (IR)
3. **AST Backend**: Generates language-native AST from IR
4. **Serializer**: Converts AST to source code
5. **Formatter** (optional): Post-processing with ruff for Python
6. **Merger** (optional): Merges with existing files to preserve custom code

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .

# Run tests
python -m pytest json_schema_to_code/tests/
```

### Project Structure

```
json_schema_to_code/
├── json_schema_to_code/
│   ├── __init__.py
│   ├── json_schema_to_code.py  # CLI entry point
│   ├── codegen.py              # Core generator logic
│   └── templates/              # Jinja2 templates
│       ├── python/
│       └── cs/
├── tests/
│   ├── schemas/                # Test schemas
│   └── test_base.py           # Test suite
└── setup.py
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Changelog

### v0.1
- Initial release
- Support for Python and C# code generation
- Basic JSON Schema features
- Command-line interface
- Configuration system
