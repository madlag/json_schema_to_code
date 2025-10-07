# Test Cases Structure

Each test case is organized in its own directory with the following structure:

```
test_case_name/
├── schema.json      # The JSON schema to test
├── config.json      # Configuration for code generation
├── reference.py     # Expected Python output (optional)
└── reference.cs     # Expected C# output (optional)
```

## Available Test Cases

### Core Functionality Tests

#### `classify/`
Tests classification schema with nested objects and arrays.
- **Validation**: Disabled
- **Features**: $ref, arrays, nested objects

#### `geometry/`
Tests geometric shapes with union types and inheritance.
- **Validation**: Disabled
- **Features**: allOf, inheritance, complex structures

#### `addition_exercise/`
Tests simple exercise schema with Literal types.
- **Validation**: Disabled
- **Features**: Literal types, defaults

### Validation Tests

#### `validation_basic/`
Tests basic validation features.
- **Validation**: Enabled
- **Features**:
  - Type checking (string, integer)
  - Required fields
  - Reference type validation
  - Array validation

#### `validation_patterns/`
Tests pattern-based string validation.
- **Validation**: Enabled
- **Features**:
  - Email pattern validation
  - Phone number patterns
  - Username patterns with length constraints
  - URL patterns

#### `validation_numeric/`
Tests numeric constraint validation.
- **Validation**: Enabled
- **Features**:
  - Minimum/maximum values
  - Exclusive minimum/maximum
  - Multiple of constraints
  - Array minItems/maxItems

## Adding New Test Cases

1. Create a new directory under `test_cases/`
2. Add `schema.json` with your JSON schema
3. Add `config.json` with code generation options:
   ```json
   {
       "add_validation": false,
       "other_options": "..."
   }
   ```
4. Generate reference files:
   ```python
   from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
   import json

   with open('schema.json') as f:
       schema = json.load(f)
   with open('config.json') as f:
       config_dict = json.load(f)

   config = CodeGeneratorConfig.from_dict(config_dict)
   codegen = CodeGenerator('YourClassName', schema, config, 'python')

   with open('reference.py', 'w') as f:
       f.write(codegen.generate())
   ```

## Running Tests

Unit tests for validation rules:
```bash
python -m pytest json_schema_to_code/tests/test_validation_rules.py -v
```

All tests:
```bash
python -m pytest json_schema_to_code/tests/ -v
```
