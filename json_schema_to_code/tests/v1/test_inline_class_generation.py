"""
Test for inline class generation, specifically for nested inline objects.
"""

import json
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def test_classification_generator_textobject_generation():
    """Test that the classification generator schema generates TextObject class correctly
    from inline object definitions."""
    # Load the schema
    schema_path = Path(__file__).parent.parent / "test_data" / "schemas" / "classification_generator.json"
    with open(schema_path) as f:
        schema = json.load(f)

    # Create generator
    config = CodeGeneratorConfig()
    codegen = CodeGenerator("ClassificationGenerator", schema, config, "python")

    # Generate code
    out = codegen.generate()

    # Verify that Items class is generated (with prefixed name from parent classes)
    assert "class ClassificationGeneratorGeneratorItems:" in out, "Items class should be generated with proper prefix"

    # Verify that Items has the expected properties
    expected_properties = [
        "text: str",
        "correct_category: str",
        "hint: str",
        "explanation: str",
        "mnemonic: str",
    ]

    for prop in expected_properties:
        assert prop in out, f"Items should have property: {prop}"

    # Verify that the main classes are generated
    assert "class ClassificationGenerator:" in out
    # Named from the 'generator' field with prefix
    assert "class ClassificationGeneratorGenerator:" in out

    # Verify that the generator property references Items with full name
    assert "items: list[ClassificationGeneratorGeneratorItems]" in out


if __name__ == "__main__":
    pytest.main([__file__])
