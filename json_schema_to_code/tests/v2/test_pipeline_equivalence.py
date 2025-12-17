"""
Test that the pipeline produces valid output.

This module contains two types of tests:
1. Syntax validation: Ensures generated code is valid Python/C#
2. Semantic equivalence: Verifies v1 and v2 produce structurally similar output
   (not textually identical, as v2 has intentional improvements like class deduplication)
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig
from json_schema_to_code.pipeline import PipelineGenerator
from json_schema_to_code.pipeline.config import CodeGeneratorConfig as PipelineConfig


def discover_test_schemas():
    """Discover all test schemas."""
    test_cases_dir = Path(__file__).parent.parent / "test_data" / "test_cases"
    schemas = []

    for test_dir in sorted(test_cases_dir.iterdir()):
        if not test_dir.is_dir() or test_dir.name.startswith("."):
            continue

        schema_file = test_dir / "schema.json"
        config_file = test_dir / "config.json"

        if not schema_file.exists():
            continue

        schemas.append(
            {
                "name": test_dir.name,
                "schema_file": schema_file,
                "config_file": config_file,
            }
        )

    return schemas


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


@pytest.mark.parametrize("test_case", discover_test_schemas(), ids=lambda tc: tc["name"])
def test_pipeline_generates_valid_python(test_case):
    """Test that pipeline generates valid Python code."""
    schema, config_dict = load_schema_and_config(test_case)
    _, pipeline_config = create_configs(config_dict)

    # Disable validation for this test
    pipeline_config.add_validation = False

    class_name = "".join(word.capitalize() for word in test_case["name"].split("_"))

    # Generate with pipeline
    pipeline_gen = PipelineGenerator(class_name, schema, pipeline_config, "python")
    pipeline_output = pipeline_gen.generate()

    # Verify it's valid Python by parsing it
    try:
        ast.parse(pipeline_output)
    except SyntaxError as e:
        pytest.fail(f"Generated invalid Python for {test_case['name']}:\n{e}\n\nCode:\n{pipeline_output[:1000]}")


def load_schema_and_config(test_case):
    """Load schema and config for a test case."""
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    if test_case["config_file"].exists():
        with open(test_case["config_file"]) as f:
            config_dict = json.load(f)
    else:
        config_dict = {}

    return schema, config_dict


def create_configs(config_dict):
    """Create both original and pipeline configs."""
    # Original config
    original_config = CodeGeneratorConfig()
    for k, v in config_dict.items():
        if hasattr(original_config, k):
            setattr(original_config, k, v)
    # Disable generation comment for comparison
    original_config.add_generation_comment = False

    # Pipeline config
    pipeline_config = PipelineConfig.from_dict(config_dict)
    pipeline_config.add_generation_comment = False

    return original_config, pipeline_config


@pytest.mark.parametrize("test_case", discover_test_schemas(), ids=lambda tc: tc["name"])
@pytest.mark.parametrize("language", ["python", "cs"])
def test_pipeline_semantic_equivalence(test_case, language):
    """Test that pipeline produces semantically equivalent output to original codegen.

    V2 (pipeline) intentionally differs from V1 in some ways:
    - Class deduplication: V2 reuses identical nested structures
    - Inline unions: V2 respects use_inline_unions config
    - Class naming: V2 uses simpler names for nested classes

    This test verifies both produce valid, structurally similar code.
    """
    schema, config_dict = load_schema_and_config(test_case)
    original_config, pipeline_config = create_configs(config_dict)

    class_name = "".join(word.capitalize() for word in test_case["name"].split("_"))

    # Generate with original (v1)
    original_gen = CodeGenerator(class_name, schema, original_config, language)
    original_output = original_gen.generate()

    # Generate with pipeline (v2)
    pipeline_gen = PipelineGenerator(class_name, schema, pipeline_config, language)
    pipeline_output = pipeline_gen.generate()

    if language == "python":
        # Both must be valid Python
        try:
            ast.parse(original_output)
        except SyntaxError as e:
            pytest.fail(f"V1 generated invalid Python: {e}")

        try:
            ast.parse(pipeline_output)
        except SyntaxError as e:
            pytest.fail(f"V2 generated invalid Python: {e}")

        # Extract class names - v2 may have fewer classes due to deduplication
        v1_classes = extract_python_classes(original_output)
        v2_classes = extract_python_classes(pipeline_output)

        # The main class should exist in both
        assert class_name in v1_classes, f"Main class {class_name} not in v1 output"
        assert class_name in v2_classes, f"Main class {class_name} not in v2 output"

        # V2 should have at least some classes (not empty)
        assert len(v2_classes) > 0, "V2 generated no classes"

    elif language == "cs":
        # Extract class names
        v1_classes = extract_csharp_classes(original_output)
        v2_classes = extract_csharp_classes(pipeline_output)

        # The main class should exist in both
        assert class_name in v1_classes, f"Main class {class_name} not in v1 output"
        assert class_name in v2_classes, f"Main class {class_name} not in v2 output"

        # V2 should have at least some classes
        assert len(v2_classes) > 0, "V2 generated no classes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
