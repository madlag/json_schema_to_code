"""
Functional tests for v3 (PipelineGeneratorV3) implementation.

These tests verify the pipeline-based code generator produces correct output
using the same test data as the v1 and v2 functional tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator


def load_all_test_cases():
    """Load all test cases from all JSON files in test_data/functional directory."""
    functional_dir = Path(__file__).parent.parent / "test_data" / "functional"
    test_cases = []

    for json_file in functional_dir.glob("*_tests.json"):
        with open(json_file) as f:
            data = json.load(f)

        for test_case in data:
            test_case["_source_file"] = json_file.name
            test_cases.append(test_case)

    return test_cases


def _generate_code(schema, config_dict, language="python", class_name="TestClass"):
    """Helper to generate code with given schema and config."""
    config = CodeGeneratorConfig()

    if config_dict:
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)

    generator = PipelineGenerator(class_name, schema, config, language)
    return generator.generate()


def _load_schema(test_case, test_data_dir):
    """Load schema from test case (either inline or from file)."""
    if "schema" in test_case:
        return test_case["schema"]
    elif "schema_file" in test_case:
        schema_path = test_data_dir / test_case["schema_file"]
        with open(schema_path) as f:
            return json.load(f)
    else:
        raise ValueError("Test case must have either 'schema' or 'schema_file'")


@pytest.mark.parametrize("test_case", load_all_test_cases())
def test_functional_generation(test_case):
    """Unified test for all JSON test cases using a single pattern."""
    name = test_case["name"]
    description = test_case["description"]
    config = test_case.get("config", {})
    source_file = test_case.get("_source_file", "unknown")

    print(f"\nTesting: {name} (from {source_file})")
    print(f"Description: {description}")

    # Load schema
    test_data_dir = Path(__file__).parent.parent / "test_data"
    schema = _load_schema(test_case, test_data_dir)

    # Test Python generation if specified
    if "expected_python" in test_case:
        generated_code = _generate_code(schema, config, "python")
        for expected in test_case["expected_python"]:
            assert expected in generated_code, f"Expected pattern '{expected}' not found in Python output"

    # Test C# generation if specified
    if "expected_cs" in test_case:
        generated_code = _generate_code(schema, config, "cs")
        for expected in test_case["expected_cs"]:
            assert expected in generated_code, f"Expected pattern '{expected}' not found in C# output"

    # Test contains patterns if specified
    if "expected_contains" in test_case:
        language = test_case.get("test_language", "python")
        generated_code = _generate_code(schema, config, language)

        for pattern in test_case["expected_contains"]:
            assert pattern in generated_code, f"Expected pattern '{pattern}' not found in {language} output"

    # Test not contains patterns if specified
    if "expected_not_contains" in test_case:
        language = test_case.get("test_language", "python")
        generated_code = _generate_code(schema, config, language)

        for pattern in test_case["expected_not_contains"]:
            assert pattern not in generated_code, f"Unexpected pattern '{pattern}' found in {language} output"


if __name__ == "__main__":
    pytest.main([__file__])
