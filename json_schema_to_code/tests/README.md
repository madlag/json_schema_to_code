# Test Structure Documentation

## Overview

This project uses a comprehensive test system with **three complementary types of tests**:

1. **Reference File Tests** - Complete output comparison tests using test cases
2. **Functional Tests** - Pattern-based tests defined in JSON files
3. **Unit Tests** - Isolated component testing (validation rules, etc.)

All tests are automatically discovered and executed, providing thorough test coverage with minimal maintenance.

## Test Types Explained

### 1. Reference File Tests (Complete Output)

**Location**: `test_data/test_cases/*/`
**Purpose**: Test complete file generation against known-good reference files
**Best for**: Regression testing, ensuring entire schemas generate correctly

Each test case is a self-contained directory with:
- `schema.json` - The JSON schema to generate code from
- `config.json` - Generator configuration options
- `reference.py` - Expected Python output
- `reference.cs` - Expected C# output (optional)

**Current test cases**:
- `addition_exercise/` - Literal types, default values
- `classify/` - $ref resolution, arrays, nested objects
- `geometry/` - allOf inheritance, complex types
- `validation_basic/` - Type checking, required fields
- `validation_patterns/` - Email, phone, username regex patterns
- `validation_numeric/` - Min/max, exclusive ranges, multipleOf

These tests ensure:
- Entire schemas generate correctly
- No regressions in output format
- Both Python and C# generation work
- Complex schemas with multiple classes work properly
- Validation code is generated correctly when enabled

### 2. Functional Tests (Pattern-Based)

**Location**: `test_data/functional/*.json`
**Purpose**: Test specific patterns, features, and edge cases in generated code
**Best for**: Feature testing, configuration options, edge cases, specific code patterns

These tests check if generated code contains or doesn't contain specific patterns. They're perfect for testing:
- Configuration options (e.g., `use_inline_unions`)
- Comment handling and filtering
- Default value generation
- Type generation patterns
- Import statement organization
- Edge cases and error conditions

### 3. Unit Tests

**Location**: `test_validation_rules.py`, `test_import_grouping.py`, etc.
**Purpose**: Test individual components in isolation
**Best for**: Testing internal logic, validation rules, utility functions

Current unit test suites:
- **`test_validation_rules.py`** - Validation rule object tests (24 tests)
- **`test_import_grouping.py`** - Python import organization tests (12 tests)
- **`test_template_simplification.py`** - Template structure tests (7 tests)
- **`test_cli_utils.py`** - CLI utility function tests (2 tests)
- **`test_inline_class_generation.py`** - Inline class generation tests

## How to Add New Tests

### Adding Reference File Tests (Recommended for complex schemas or validation)

**Step 1**: Create a new test case directory in `test_data/test_cases/`:

```bash
mkdir test_data/test_cases/my_new_test/
```

**Step 2**: Create `schema.json` with your JSON schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "definitions": {
    "MyClass": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {"type": "string", "minLength": 1},
        "value": {"type": "number", "minimum": 0}
      }
    }
  }
}
```

**Step 3**: Create `config.json` to control generation options:

```json
{
  "add_validation": true
}
```

Available config options:
- `add_validation` (bool) - Generate validation code in `__post_init__`
- `use_inline_unions` (bool) - Generate inline union types
- `exclude_metadata` (bool) - Exclude metadata fields
- `add_generation_comment` (bool) - Add generation comment header

**Step 4**: Generate reference files:

```bash
# Generate Python reference
python -c "
from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
import json

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/schema.json') as f:
    schema = json.load(f)

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/config.json') as f:
    config_data = json.load(f)

config = CodeGeneratorConfig()
config.add_validation = config_data.get('add_validation', False)
config.use_inline_unions = config_data.get('use_inline_unions', False)

generator = CodeGenerator('MyClass', schema, config, 'python')
output = generator.generate()

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/reference.py', 'w') as f:
    f.write(output)
"

# Generate C# reference (optional)
python -c "
from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
import json

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/schema.json') as f:
    schema = json.load(f)

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/config.json') as f:
    config_data = json.load(f)

config = CodeGeneratorConfig()
config.add_validation = config_data.get('add_validation', False)

generator = CodeGenerator('MyClass', schema, config, 'cs')
output = generator.generate()

with open('json_schema_to_code/tests/test_data/test_cases/my_new_test/reference.cs', 'w') as f:
    f.write(output)
"
```

**Step 5**: Run tests - your schema will be automatically discovered and tested!

```bash
python -m pytest json_schema_to_code/tests/test_reference_files.py -v
```

### Adding Functional Tests (For specific patterns)

**Step 1**: Create or modify a JSON file in `test_data/functional/` following this pattern:

```json
[
  {
    "name": "test_name",
    "description": "Description of what this test does",
    "config": {
      "use_inline_unions": false,
      "other_config_option": "value"
    },
    "schema": {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "definitions": {
        "MyClass": {
          "type": "object",
          "properties": {
            "name": {"type": "string"}
          }
        }
      }
    },
    "expected_contains": [
      "pattern that should be in generated code",
      "class MyClass"
    ],
    "expected_not_contains": [
      "pattern that should NOT be in generated code"
    ]
  }
]
```

**Step 2**: Run tests - your new test will be automatically discovered and executed!

### Adding Unit Tests (For validation rules or utilities)

**Step 1**: Add test methods to existing test files or create new ones:

```python
# In test_validation_rules.py
def test_my_validation_rule_python(self):
    """Test MyValidationRule generates correct Python code"""
    rule = MyValidationRule("my_field", "python", some_param=123)
    code = rule.generate_code()

    assert len(code) == 2
    assert code[0] == "if self.my_field < 123:"
    assert 'raise ValueError' in code[1]
```

## Test File Organization

### Directory Structure

```
test_data/
├── functional/              # Pattern-based functional tests
│   ├── comment_handling_tests.json
│   ├── default_values_tests.json
│   ├── exclude_metadata_tests.json
│   ├── generation_comment_tests.json
│   ├── quoted_types_tests.json
│   ├── ui_hierarchy_tests.json
│   └── union_types_tests.json
└── test_cases/              # Self-contained test cases
    ├── README.md
    ├── addition_exercise/
    │   ├── schema.json
    │   ├── config.json
    │   ├── reference.py
    │   └── reference.cs
    ├── classify/
    │   ├── schema.json
    │   ├── config.json
    │   └── reference.py
    ├── geometry/
    │   ├── schema.json
    │   ├── config.json
    │   ├── reference.py
    │   └── reference.cs
    ├── validation_basic/
    │   ├── schema.json
    │   ├── config.json
    │   └── reference.py
    ├── validation_numeric/
    │   ├── schema.json
    │   ├── config.json
    │   └── reference.py
    └── validation_patterns/
        ├── schema.json
        ├── config.json
        └── reference.py
```

### Python Test Files

1. **`test_reference_files.py`** - Reference file comparison tests (8 tests)
2. **`test_validation_rules.py`** - Validation rule unit tests (24 tests)
3. **`test_functional.py`** - Main test runner for functional tests (32 tests)
4. **`test_import_grouping.py`** - Python import organization tests (12 tests)
5. **`test_template_simplification.py`** - Template structure tests (7 tests)
6. **`test_cli_utils.py`** - CLI utility function tests (2 tests)
7. **`test_inline_class_generation.py`** - Inline class generation tests

## Running Tests

```bash
# Run all tests
python -m pytest json_schema_to_code/tests/

# Run only reference file tests
python -m pytest json_schema_to_code/tests/test_reference_files.py

# Run only validation rule tests
python -m pytest json_schema_to_code/tests/test_validation_rules.py

# Run only functional tests
python -m pytest json_schema_to_code/tests/test_functional.py

# Run with verbose output
python -m pytest json_schema_to_code/tests/ -v

# Run a specific test
python -m pytest json_schema_to_code/tests/test_reference_files.py::test_reference_file_generation[validation_basic_python] -v
```

## Validation Feature

The validation feature generates runtime validation code in Python's `__post_init__` method and C#'s constructor. It supports:

### Supported Validation Rules

**Type Validation**:
- `type` - Basic type checking (string, number, boolean, array, object)
- `$ref` - Reference type checking for custom classes

**String Validation**:
- `minLength` - Minimum string length (also enforces non-empty for required fields)
- `maxLength` - Maximum string length
- `pattern` - Regex pattern matching

**Numeric Validation**:
- `minimum` - Minimum value (inclusive)
- `maximum` - Maximum value (inclusive)
- `exclusiveMinimum` - Minimum value (exclusive)
- `exclusiveMaximum` - Maximum value (exclusive)
- `multipleOf` - Value must be a multiple of specified number

**Array Validation**:
- `minItems` - Minimum array length
- `maxItems` - Maximum array length
- `items.type` - Type checking for array elements

**Enum/Const Validation**:
- `enum` - Value must be in enumeration
- `const` - Value must equal constant

### Example

Given this schema with validation enabled:

```json
{
  "definitions": {
    "User": {
      "type": "object",
      "required": ["username", "age"],
      "properties": {
        "username": {
          "type": "string",
          "pattern": "^[a-zA-Z0-9_]{3,20}$"
        },
        "age": {
          "type": "number",
          "minimum": 0,
          "maximum": 150
        }
      }
    }
  }
}
```

Generates Python code with validation:

```python
@dataclass
class User:
    username: str
    age: float

    def __post_init__(self):
        """Validate the object after initialization."""
        if not isinstance(self.username, str):
            raise ValueError("username must be a string")
        if not self.username:
            raise ValueError("username field is required and cannot be empty")
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", self.username):
            raise ValueError(f"username must match pattern ^[a-zA-Z0-9_]{3,20}$, got {self.username}")
        if not isinstance(self.age, (int, float)):
            raise ValueError("age must be a number")
        if self.age < 0:
            raise ValueError(f"age must be >= 0, got {self.age}")
        if self.age > 150:
            raise ValueError(f"age must be <= 150, got {self.age}")
```

## Test Development Workflow

### For New Features

1. **Start with unit tests** - If adding new validation rules or utilities
2. **Add functional tests** - Add patterns to `test_data/functional/`
3. **Test edge cases** - Add multiple test cases covering different scenarios
4. **Add reference tests** - For complex schemas, add complete test cases
5. **Run tests frequently** - Tests are fast and provide immediate feedback

### For Bug Fixes

1. **Reproduce with a test** - Add a test that fails with the current bug
2. **Fix the code** - Implement the fix
3. **Verify test passes** - Ensure the test now passes
4. **Update references if needed** - If output format changed, regenerate reference files

### For Validation Rules

1. **Add unit tests** - Test the validation rule in isolation
2. **Add reference test** - Create a test case with schema using the rule
3. **Verify both languages** - Ensure Python and C# both work correctly

## Benefits of This Approach

- **Self-contained test cases** - Each test has schema, config, and references together
- **Easy to add tests** - Just add directories and JSON files
- **Comprehensive coverage** - Unit tests, pattern tests, and complete output testing
- **Language agnostic** - Test both Python and C# generation easily
- **Fast feedback** - Tests run quickly and provide clear failure messages
- **Maintainable** - Test logic is centralized and well-organized
- **Readable** - Test cases are self-documenting JSON
- **Automatic discovery** - New tests are automatically found and executed
- **Flexible configuration** - Each test case can have its own generation options

## Current Test Coverage

```
Total: 85+ tests across all test files

- Reference file tests: 8 tests
- Validation rule unit tests: 24 tests
- Functional tests: 32 tests
- Import grouping tests: 12 tests
- Template tests: 7 tests
- CLI tests: 2 tests
```

All tests pass consistently and provide immediate feedback on code changes.
