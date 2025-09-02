import json
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def load_test_data():
    """Load test cases from JSON file"""
    test_data_path = Path(__file__).parent / "test_data" / "exclude_metadata_tests.json"
    with open(test_data_path) as f:
        return json.load(f)


@pytest.mark.parametrize("test_case", load_test_data())
def test_exclude_metadata_python(test_case):
    """Test exclude metadata generation for Python"""
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

    # Also verify that the config import is included when using exclude metadata
    if config.exclude_default_value_from_json:
        assert (
            "from dataclasses_json import config" in output
        ), "config import missing when exclude metadata is enabled"


def test_exclude_metadata_config_option():
    """Test that the exclude_default_value_from_json config option works correctly"""
    # Test with exclude metadata enabled
    config_enabled = CodeGeneratorConfig()
    config_enabled.exclude_default_value_from_json = True

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "TestClass": {
                "type": "object",
                "properties": {"field_with_default": {"type": "string", "default": "test"}},
            }
        },
    }

    generator_enabled = CodeGenerator("TestClass", schema, config_enabled, "python")
    output_enabled = generator_enabled.generate()

    # Should contain field with metadata
    assert 'field(default="test", metadata=config(exclude=lambda x: x == "test"))' in output_enabled

    # Test with exclude metadata disabled (default)
    config_disabled = CodeGeneratorConfig()
    config_disabled.exclude_default_value_from_json = False

    generator_disabled = CodeGenerator("TestClass", schema, config_disabled, "python")
    output_disabled = generator_disabled.generate()

    # Should contain simple default assignment
    assert 'field_with_default: str = "test"' in output_disabled
    assert "metadata=config" not in output_disabled


def test_exclude_metadata_cs_language():
    """Test that exclude metadata is not applied for C# language"""
    config = CodeGeneratorConfig()
    config.exclude_default_value_from_json = True

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "TestClass": {
                "type": "object",
                "properties": {"field_with_default": {"type": "string", "default": "test"}},
            }
        },
    }

    generator = CodeGenerator("TestClass", schema, config, "cs")
    output = generator.generate()

    # C# output should not contain Python metadata
    assert "metadata=config" not in output
    assert "field(" not in output
    assert 'public string field_with_default = "test";' in output


if __name__ == "__main__":
    pytest.main([__file__])
