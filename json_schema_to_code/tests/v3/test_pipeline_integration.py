"""
Integration tests for the V3 pipeline using real-world schemas.

These tests use schemas from the test_data/pipeline/integration directory
and verify that V3 generates valid code.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from json_schema_to_code.pipeline_v3 import PipelineGeneratorV3
from json_schema_to_code.pipeline_v3.config import CodeGeneratorConfig


def discover_integration_schemas():
    """Discover all integration test schemas."""
    integration_dir = Path(__file__).parent.parent / "test_data" / "pipeline" / "integration"
    schemas = []

    for schema_file in sorted(integration_dir.glob("*.json")):
        schemas.append(
            {
                "name": schema_file.stem.replace("_schema", ""),
                "schema_file": schema_file,
            }
        )

    return schemas


def get_class_name(name: str) -> str:
    """Convert schema name to class name."""
    return "".join(word.capitalize() for word in name.split("_"))


def extract_python_classes(code: str) -> set[str]:
    """Extract class names from Python code."""
    try:
        tree = ast.parse(code)
        return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    except SyntaxError:
        return set()


def extract_csharp_classes(code: str) -> set[str]:
    """Extract class names from C# code using regex."""
    pattern = r"public class (\w+)"
    return set(re.findall(pattern, code))


@pytest.mark.parametrize("test_case", discover_integration_schemas(), ids=lambda tc: tc["name"])
def test_v3_generates_valid_python_integration(test_case):
    """Test that V3 generates valid Python code for integration schemas."""
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    config = CodeGeneratorConfig()
    config.add_generation_comment = False

    class_name = get_class_name(test_case["name"])

    try:
        gen = PipelineGeneratorV3(class_name, schema, config, "python")
        code = gen.generate()

        # Verify it's valid Python
        ast.parse(code)
    except Exception as e:
        pytest.fail(f"V3 failed for {test_case['name']}: {e}")


@pytest.mark.parametrize("test_case", discover_integration_schemas(), ids=lambda tc: tc["name"])
def test_v3_generates_valid_csharp_integration(test_case):
    """Test that V3 generates valid C# code for integration schemas."""
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    config = CodeGeneratorConfig()
    config.add_generation_comment = False

    class_name = get_class_name(test_case["name"])

    try:
        gen = PipelineGeneratorV3(class_name, schema, config, "cs")
        code = gen.generate()

        # Basic validation - should have class declarations
        classes = extract_csharp_classes(code)
        assert len(classes) > 0, f"No classes generated for {test_case['name']}"
    except Exception as e:
        pytest.fail(f"V3 C# failed for {test_case['name']}: {e}")


@pytest.mark.parametrize("test_case", discover_integration_schemas(), ids=lambda tc: tc["name"])
def test_v3_generates_classes_integration(test_case):
    """Test that V3 generates at least one class for each schema."""
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    config = CodeGeneratorConfig()
    config.add_generation_comment = False

    class_name = get_class_name(test_case["name"])

    # Python
    gen = PipelineGeneratorV3(class_name, schema, config, "python")
    code = gen.generate()
    classes = extract_python_classes(code)
    assert len(classes) > 0, f"V3 Python generated no classes for {test_case['name']}"

    # C#
    gen_cs = PipelineGeneratorV3(class_name, schema, config, "cs")
    code_cs = gen_cs.generate()
    classes_cs = extract_csharp_classes(code_cs)
    assert len(classes_cs) > 0, f"V3 C# generated no classes for {test_case['name']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
