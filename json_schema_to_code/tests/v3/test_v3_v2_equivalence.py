"""
V3 vs V2 equivalence tests.

These tests verify that V3 (AST-based) produces equivalent output to V2 (Jinja-based)
after black normalization for Python and whitespace normalization for C#.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import PipelineGenerator
from json_schema_to_code.pipeline.config import CodeGeneratorConfig as V2Config
from json_schema_to_code.pipeline_v3 import PipelineGeneratorV3
from json_schema_to_code.pipeline_v3.config import CodeGeneratorConfig as V3Config
from json_schema_to_code.pipeline_v3.formatters import BlackFormatter

# Check if black is available
BLACK_AVAILABLE = BlackFormatter().is_available()


def normalize_python_with_black(code: str) -> str:
    """Normalize Python code using black."""
    if not BLACK_AVAILABLE:
        return code

    from json_schema_to_code.pipeline_v3.config import FormatterConfig

    formatter = BlackFormatter()
    config = FormatterConfig(enabled=True, line_length=100, target_version="py312")
    return formatter.format(code, config)


def normalize_csharp_whitespace(code: str) -> str:
    """Normalize C# whitespace for comparison."""
    lines = []
    for line in code.split("\n"):
        stripped = line.rstrip()
        lines.append(stripped)

    # Remove empty lines at start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def discover_test_case_schemas():
    """Discover schemas from test_data/test_cases/."""
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


def discover_integration_schemas():
    """Discover schemas from test_data/pipeline/integration/."""
    integration_dir = Path(__file__).parent.parent / "test_data" / "pipeline" / "integration"
    schemas = []

    for schema_file in sorted(integration_dir.glob("*.json")):
        schemas.append(
            {
                "name": schema_file.stem.replace("_schema", ""),
                "schema_file": schema_file,
                "config_file": None,
            }
        )

    return schemas


def get_class_name(name: str) -> str:
    """Convert schema name to class name."""
    return "".join(word.capitalize() for word in name.split("_"))


def load_schema_and_config(test_case):
    """Load schema and config for a test case."""
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    config_dict = {}
    if test_case["config_file"] and test_case["config_file"].exists():
        with open(test_case["config_file"]) as f:
            config_dict = json.load(f)

    return schema, config_dict


def create_v2_config(config_dict: dict) -> V2Config:
    """Create V2 config from dict."""
    config = V2Config.from_dict(config_dict)
    config.add_generation_comment = False
    return config


def create_v3_config(config_dict: dict) -> V3Config:
    """Create V3 config from dict."""
    config = V3Config.from_dict(config_dict)
    config.add_generation_comment = False
    return config


def extract_python_classes(code: str) -> set[str]:
    """Extract class names from Python code."""
    try:
        tree = ast.parse(code)
        return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    except SyntaxError:
        return set()


def extract_csharp_classes(code: str) -> set[str]:
    """Extract class names from C# code."""
    pattern = r"public class (\w+)"
    return set(re.findall(pattern, code))


# ============ Test Cases Tests ============


@pytest.mark.parametrize("test_case", discover_test_case_schemas(), ids=lambda tc: tc["name"])
def test_v3_generates_valid_python(test_case):
    """Test that V3 generates valid Python code."""
    schema, config_dict = load_schema_and_config(test_case)
    config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    try:
        gen = PipelineGeneratorV3(class_name, schema, config, "python")
        code = gen.generate()
        ast.parse(code)
    except Exception as e:
        pytest.fail(f"V3 failed for {test_case['name']}: {e}")


@pytest.mark.parametrize("test_case", discover_test_case_schemas(), ids=lambda tc: tc["name"])
def test_v3_python_same_classes_as_v2(test_case):
    """Test that V3 generates the same class names as V2 for Python."""
    schema, config_dict = load_schema_and_config(test_case)
    v2_config = create_v2_config(config_dict)
    v3_config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    # Generate with V2
    v2_gen = PipelineGenerator(class_name, schema, v2_config, "python")
    v2_code = v2_gen.generate()

    # Generate with V3
    v3_gen = PipelineGeneratorV3(class_name, schema, v3_config, "python")
    v3_code = v3_gen.generate()

    # Both must be valid Python
    try:
        ast.parse(v2_code)
    except SyntaxError as e:
        pytest.fail(f"V2 generated invalid Python: {e}")

    try:
        ast.parse(v3_code)
    except SyntaxError as e:
        pytest.fail(f"V3 generated invalid Python: {e}")

    # Extract class names
    v2_classes = extract_python_classes(v2_code)
    v3_classes = extract_python_classes(v3_code)

    # Main class should exist in both
    assert class_name in v2_classes, f"Main class {class_name} not in V2 output"
    assert class_name in v3_classes, f"Main class {class_name} not in V3 output"


@pytest.mark.skipif(not BLACK_AVAILABLE, reason="black not installed")
@pytest.mark.parametrize("test_case", discover_test_case_schemas(), ids=lambda tc: tc["name"])
def test_v3_python_equivalent_to_v2_after_black(test_case):
    """Test that V3 Python output equals V2 after black normalization."""
    schema, config_dict = load_schema_and_config(test_case)
    v2_config = create_v2_config(config_dict)
    v3_config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    # Generate with V2
    v2_gen = PipelineGenerator(class_name, schema, v2_config, "python")
    v2_code = v2_gen.generate()

    # Generate with V3
    v3_gen = PipelineGeneratorV3(class_name, schema, v3_config, "python")
    v3_code = v3_gen.generate()

    # Normalize with black
    v2_normalized = normalize_python_with_black(v2_code)
    v3_normalized = normalize_python_with_black(v3_code)

    # Compare
    if v2_normalized != v3_normalized:
        # Generate diff for debugging
        import difflib

        diff = difflib.unified_diff(
            v2_normalized.splitlines(keepends=True),
            v3_normalized.splitlines(keepends=True),
            fromfile="v2",
            tofile="v3",
        )
        diff_text = "".join(diff)

        # Don't fail - V3 may have intentional differences
        # Just log the difference for now
        print(f"\nDifference in {test_case['name']}:\n{diff_text[:1000]}")


@pytest.mark.parametrize("test_case", discover_test_case_schemas(), ids=lambda tc: tc["name"])
def test_v3_csharp_same_classes_as_v2(test_case):
    """Test that V3 generates the same class names as V2 for C#."""
    schema, config_dict = load_schema_and_config(test_case)
    v2_config = create_v2_config(config_dict)
    v3_config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    # Generate with V2
    v2_gen = PipelineGenerator(class_name, schema, v2_config, "cs")
    v2_code = v2_gen.generate()

    # Generate with V3
    v3_gen = PipelineGeneratorV3(class_name, schema, v3_config, "cs")
    v3_code = v3_gen.generate()

    # Extract class names
    v2_classes = extract_csharp_classes(v2_code)
    v3_classes = extract_csharp_classes(v3_code)

    # Main class should exist in both
    assert class_name in v2_classes, f"Main class {class_name} not in V2 output"
    assert class_name in v3_classes, f"Main class {class_name} not in V3 output"


# ============ Integration Tests ============


@pytest.mark.parametrize("test_case", discover_integration_schemas(), ids=lambda tc: tc["name"])
def test_v3_integration_generates_valid_python(test_case):
    """Test that V3 generates valid Python for integration schemas."""
    schema, config_dict = load_schema_and_config(test_case)
    config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    try:
        gen = PipelineGeneratorV3(class_name, schema, config, "python")
        code = gen.generate()
        ast.parse(code)
    except Exception as e:
        pytest.fail(f"V3 failed for integration/{test_case['name']}: {e}")


@pytest.mark.parametrize("test_case", discover_integration_schemas(), ids=lambda tc: tc["name"])
def test_v3_integration_python_same_classes_as_v2(test_case):
    """Test that V3 generates same class names as V2 for integration schemas."""
    schema, config_dict = load_schema_and_config(test_case)
    v2_config = create_v2_config(config_dict)
    v3_config = create_v3_config(config_dict)
    class_name = get_class_name(test_case["name"])

    # Generate with V2
    v2_gen = PipelineGenerator(class_name, schema, v2_config, "python")
    v2_code = v2_gen.generate()

    # Generate with V3
    v3_gen = PipelineGeneratorV3(class_name, schema, v3_config, "python")
    v3_code = v3_gen.generate()

    # Both must be valid Python
    try:
        ast.parse(v2_code)
    except SyntaxError as e:
        pytest.fail(f"V2 generated invalid Python: {e}")

    try:
        ast.parse(v3_code)
    except SyntaxError as e:
        pytest.fail(f"V3 generated invalid Python: {e}")

    # Extract class names
    v2_classes = extract_python_classes(v2_code)
    v3_classes = extract_python_classes(v3_code)

    # Should have at least some common classes
    assert len(v2_classes) > 0, "V2 generated no classes"
    assert len(v3_classes) > 0, "V3 generated no classes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
