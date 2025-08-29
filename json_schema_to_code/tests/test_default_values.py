import json
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def load_test_data():
    """Load test cases from JSON file"""
    test_data_path = Path(__file__).parent / "test_data" / "default_values_tests.json"
    with open(test_data_path) as f:
        return json.load(f)


@pytest.mark.parametrize("test_case", load_test_data())
def test_default_values_python(test_case):
    """Test default value generation for Python"""
    config = CodeGeneratorConfig()

    # Apply config if provided in test case
    if "config" in test_case:
        for key, value in test_case["config"].items():
            setattr(config, key, value)

    generator = CodeGenerator("TestClass", test_case["schema"], config, "python")
    output = generator.generate()

    # Check each expected pattern in the generated output
    for expected in test_case["expected_python"]:
        assert expected in output, f"Expected '{expected}' not found in output:\n{output}"


@pytest.mark.parametrize("test_case", load_test_data())
def test_default_values_cs(test_case):
    """Test default value generation for C#"""
    config = CodeGeneratorConfig()

    # Apply config if provided in test case
    if "config" in test_case:
        for key, value in test_case["config"].items():
            setattr(config, key, value)

    generator = CodeGenerator("TestClass", test_case["schema"], config, "cs")
    output = generator.generate()

    # Check each expected pattern in the generated output
    for expected in test_case["expected_cs"]:
        assert expected in output, f"Expected '{expected}' not found in output:\n{output}"


if __name__ == "__main__":
    pytest.main([__file__])
