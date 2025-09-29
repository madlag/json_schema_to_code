# Test Structure Documentation

## Overview

This project uses a comprehensive test system with **two complementary types of tests**:

1. **Functional Tests** - Pattern-based tests defined in JSON files
2. **Reference File Tests** - Complete output comparison tests

Both types are automatically discovered and executed, providing thorough test coverage with minimal maintenance.

## Test Types Explained

### 1. Functional Tests (Pattern-Based)

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

### 2. Reference File Tests (Complete Output)

**Location**: `test_data/schemas/*.json` + `test_data/references/*`
**Purpose**: Test complete file generation against known-good reference files
**Best for**: Regression testing, ensuring entire schemas generate correctly

These tests generate complete files and compare them against reference files. They ensure:
- Entire schemas generate correctly
- No regressions in output format
- Both Python and C# generation work
- Complex schemas with multiple classes work properly

## How to Add New Tests

### Adding Functional Tests (Recommended for most features)

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

### Adding Reference File Tests (For complete schemas)

**Step 1**: Add your schema to `test_data/schemas/my_schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "definitions": {
    "MyClass": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "value": {"type": "number"}
      }
    }
  }
}
```

**Step 2**: Generate reference files for both languages:

```bash
# Generate Python reference
python -c "
from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
import json

with open('json_schema_to_code/tests/test_data/schemas/my_schema.json') as f:
    schema = json.load(f)

config = CodeGeneratorConfig()
config.use_inline_unions = False

generator = CodeGenerator('MyClass', schema, config, 'python')
output = generator.generate()

with open('json_schema_to_code/tests/test_data/references/my_schema.python', 'w') as f:
    f.write(output)
"

# Generate C# reference
python -c "
from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
import json

with open('json_schema_to_code/tests/test_data/schemas/my_schema.json') as f:
    schema = json.load(f)

config = CodeGeneratorConfig()
config.use_inline_unions = False

generator = CodeGenerator('MyClass', schema, config, 'cs')
output = generator.generate()

with open('json_schema_to_code/tests/test_data/references/my_schema.cs', 'w') as f:
    f.write(output)
"
```

**Step 3**: Run tests - your schema will be automatically tested against both reference files!

## Advanced Test Patterns

### Using External Schema Files

Instead of inline schemas, reference external files:

```json
[
  {
    "name": "test_name",
    "description": "Test using external schema file",
    "schema_file": "schemas/my_schema.json",
    "expected_contains": ["expected pattern"]
  }
]
```

### Language-Specific Tests

For tests that need different expectations per language:

```json
[
  {
    "name": "test_name",
    "description": "Test with language-specific expectations",
    "schema": { /* schema */ },
    "expected_python": [
      "from dataclasses import dataclass"
    ],
    "expected_cs": [
      "public class MyClass"
    ]
  }
]
```

### Test Language Override

By default, functional tests run against Python output. To test C# output:

```json
[
  {
    "name": "test_name",
    "description": "Test C# generation",
    "test_language": "cs",
    "schema": { /* schema */ },
    "expected_contains": ["public class"]
  }
]
```

## Test File Organization

### Directory Structure

```
test_data/
├── functional/           # Pattern-based functional tests
│   ├── comment_handling_tests.json
│   ├── default_values_tests.json
│   ├── exclude_metadata_tests.json
│   ├── generation_comment_tests.json
│   ├── quoted_types_tests.json
│   ├── ui_hierarchy_tests.json
│   └── union_types_tests.json
├── schemas/             # Input schemas for reference tests
│   ├── addition_exercise.json
│   ├── dhclient.json
│   ├── geometry.json
│   └── ui_hierarchy_schema.json
└── references/          # Expected output for reference tests
    ├── addition_exercise.python
    ├── addition_exercise.cs
    ├── dhclient.python
    ├── dhclient.cs
    ├── geometry.python
    ├── geometry.cs
    ├── ui_hierarchy_schema.python
    └── ui_hierarchy_schema.cs
```

### Python Test Files

1. **`test_functional.py`** - Main test runner for functional tests (32 tests)
2. **`test_reference_files.py`** - Reference file comparison tests (8 tests)
3. **`test_import_grouping.py`** - Python import organization tests (12 tests)
4. **`test_template_simplification.py`** - Template structure tests (7 tests)
5. **`test_cli_utils.py`** - CLI utility function tests (2 tests)

## Running Tests

```bash
# Run all tests
python -m pytest json_schema_to_code/tests/

# Run only functional tests
python -m pytest json_schema_to_code/tests/test_functional.py

# Run only reference file tests
python -m pytest json_schema_to_code/tests/test_reference_files.py

# Run with verbose output
python -m pytest json_schema_to_code/tests/ -v
```

## Test Development Workflow

### For New Features

1. **Start with functional tests** - Add patterns to `test_data/functional/`
2. **Test edge cases** - Add multiple test cases covering different scenarios
3. **Add reference tests** - For complex schemas, add complete reference files
4. **Run tests frequently** - Tests are fast and provide immediate feedback

### For Bug Fixes

1. **Reproduce with functional test** - Add a test that fails with the current bug
2. **Fix the code** - Implement the fix
3. **Verify test passes** - Ensure the functional test now passes
4. **Update references if needed** - If output format changed, update reference files

## Benefits of This Approach

- **Easy to add tests** - Just add JSON files, no Python code needed
- **Comprehensive coverage** - Both pattern-based and complete output testing
- **Language agnostic** - Test both Python and C# generation easily
- **Fast feedback** - Tests run quickly and provide clear failure messages
- **Maintainable** - Test logic is centralized and well-organized
- **Readable** - Test cases are self-documenting JSON
- **Automatic discovery** - New tests are automatically found and executed

## Migration from Old Pattern

The old pattern required separate Python test files for each feature. The new unified pattern consolidates all JSON-based tests into organized directories while maintaining comprehensive test coverage and making it much easier to add new tests.
