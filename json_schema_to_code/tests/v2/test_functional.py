"""
Functional tests for v2 (PipelineGenerator) implementation.

These tests verify the pipeline-based code generator produces correct output
using the same test data as the v1 functional tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import PipelineGenerator
from json_schema_to_code.pipeline.config import CodeGeneratorConfig


def load_all_test_cases():
    """Load all test cases from all JSON files in test_data/functional directory"""
    functional_dir = Path(__file__).parent.parent / "test_data" / "functional"
    test_cases = []

    # Find all *_tests.json files
    for json_file in functional_dir.glob("*_tests.json"):
        with open(json_file) as f:
            data = json.load(f)

        for test_case in data:
            # Add source file info for debugging
            test_case["_source_file"] = json_file.name
            test_cases.append(test_case)

    return test_cases


def _generate_code(schema, config_dict, language="python", class_name="TestClass"):
    """Helper to generate code with given schema and config"""
    config = CodeGeneratorConfig()

    # Apply config if provided
    if config_dict:
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)

    generator = PipelineGenerator(class_name, schema, config, language)
    return generator.generate()


def _load_schema(test_case, test_data_dir):
    """Load schema from test case (either inline or from file)"""
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
    """Unified test for all JSON test cases using a single pattern"""
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
    # V2 uses Jinja (double quotes), but expected_python uses single quotes for V3 compatibility
    # Use expected_python_v2 if available, otherwise expected_python with quote conversion
    if "expected_python_v2" in test_case:
        expected_python = test_case["expected_python_v2"]
        use_quote_conversion = False
    elif "expected_python" in test_case:
        expected_python = test_case["expected_python"]
        use_quote_conversion = True
    else:
        expected_python = None

    if expected_python:
        generated_code = _generate_code(schema, config, "python")
        for expected in expected_python:
            # Convert single quotes to double quotes for V2 comparison if needed
            expected_v2 = expected.replace("'", '"') if use_quote_conversion else expected
            assert expected_v2 in generated_code, f"Expected pattern '{expected_v2}' not found in Python output"

    # Test C# generation if specified
    if "expected_cs" in test_case:
        generated_code = _generate_code(schema, config, "cs")
        for expected in test_case["expected_cs"]:
            assert expected in generated_code, f"Expected pattern '{expected}' not found in C# output"

    # Test contains patterns if specified
    if "expected_contains" in test_case:
        # Default to Python unless language is specified
        language = test_case.get("test_language", "python")
        generated_code = _generate_code(schema, config, language)

        for pattern in test_case["expected_contains"]:
            # Convert single quotes to double quotes for V2 comparison
            pattern_v2 = pattern.replace("'", '"')
            assert pattern_v2 in generated_code, f"Expected pattern '{pattern_v2}' not found in {language} output"

    # Test not contains patterns if specified
    if "expected_not_contains" in test_case:
        # Default to Python unless language is specified
        language = test_case.get("test_language", "python")
        generated_code = _generate_code(schema, config, language)

        for pattern in test_case["expected_not_contains"]:
            # Convert single quotes to double quotes for V2 comparison
            pattern_v2 = pattern.replace("'", '"')
            assert pattern_v2 not in generated_code, f"Unexpected pattern '{pattern_v2}' found in {language} output"


if __name__ == "__main__":
    pytest.main([__file__])
