"""
Tests for external base class import generation.

When a schema uses allOf with a $ref to an external schema, the generated
Python code should include the appropriate import for the base class.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator

TEST_DATA_DIR = Path(__file__).with_name("test_data") / "pipeline" / "external_base_class"


def load_schema(name: str) -> dict:
    """Load a schema from the test data directory."""
    with open(TEST_DATA_DIR / name) as f:
        return json.load(f)


def extract_imports(code: str) -> list[tuple[str, list[str]]]:
    """Extract import statements from Python code.

    Returns a list of (module, names) tuples.
    """
    tree = ast.parse(code)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names]
            imports.append((node.module, names))
    return imports


def test_external_base_class_generates_import():
    """Test that external base class generates proper import."""
    schema = load_schema("child_schema.json")

    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    config.external_ref_base_module = "explayn_dh_agent.barbara.db.app_object_definitions"

    gen = PipelineGenerator("QuizData", schema, config, "python")
    code = gen.generate()

    # Parse the code to extract imports
    imports = extract_imports(code)

    # Find imports from the external module
    external_imports = [(module, names) for module, names in imports if "base_dataclass" in module]

    # Should have imports for ActivityProblem, ActivityState, ActivityData
    imported_names = set()
    for module, names in external_imports:
        imported_names.update(names)

    # QuizProblem extends ActivityProblem, QuizState extends ActivityState,
    # QuizData extends ActivityData - all should be imported
    assert "ActivityProblem" in imported_names, f"ActivityProblem should be imported. Found imports: {external_imports}"
    assert "ActivityState" in imported_names, f"ActivityState should be imported. Found imports: {external_imports}"
    assert "ActivityData" in imported_names, f"ActivityData should be imported. Found imports: {external_imports}"


def test_external_base_class_generates_valid_python():
    """Test that generated code with external base classes is valid Python."""
    schema = load_schema("child_schema.json")

    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    config.external_ref_base_module = "explayn_dh_agent.barbara.db.app_object_definitions"

    gen = PipelineGenerator("QuizData", schema, config, "python")
    code = gen.generate()

    # Should be valid Python syntax
    ast.parse(code)


def test_no_external_import_without_config():
    """Test that no external imports are generated without external_ref_base_module."""
    schema = load_schema("child_schema.json")

    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    # external_ref_base_module is NOT set

    gen = PipelineGenerator("QuizData", schema, config, "python")
    code = gen.generate()

    # Parse the code to extract imports
    imports = extract_imports(code)

    # Should not have any imports from external modules
    external_imports = [(module, names) for module, names in imports if "base_dataclass" in module or "app_object" in module]

    assert len(external_imports) == 0, f"Should not have external imports without config. Found: {external_imports}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
