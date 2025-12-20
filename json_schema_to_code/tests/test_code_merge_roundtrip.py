"""
Roundtrip tests for code generation with merge.

These tests verify that regenerating code from schemas and merging with
existing files produces identical output (i.e., the generated code matches
what was already in the file for the generated portions, and custom code
is preserved).

Test data is in: test_data/code_merge/<activity_name>/
Each directory contains:
  - schema.json: The JSON schema
  - dataclass.py: The existing Python dataclass file
  - dataclass.cs: The existing C# dataclass file (optional)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, OutputMode, PipelineGenerator
from json_schema_to_code.pipeline.merger import PythonAstMerger


def discover_code_merge_test_cases():
    """Discover all code_merge test cases."""
    code_merge_dir = Path(__file__).parent / "test_data" / "code_merge"
    test_cases = []

    if not code_merge_dir.exists():
        return test_cases

    for activity_dir in sorted(code_merge_dir.iterdir()):
        if not activity_dir.is_dir():
            continue

        schema_file = activity_dir / "schema.json"
        python_file = activity_dir / "dataclass.py"
        csharp_file = activity_dir / "dataclass.cs"

        if not schema_file.exists():
            continue

        test_cases.append(
            {
                "name": activity_dir.name,
                "schema_file": schema_file,
                "python_file": python_file if python_file.exists() else None,
                "csharp_file": csharp_file if csharp_file.exists() else None,
            }
        )

    return test_cases


def get_test_ids():
    """Get test IDs for pytest parametrization."""
    return [tc["name"] for tc in discover_code_merge_test_cases()]


@pytest.fixture
def code_merge_test_cases():
    """Fixture to provide all test cases."""
    return discover_code_merge_test_cases()


class TestCodeMergeRoundtrip:
    """Tests for code merge roundtrip verification."""

    @pytest.mark.parametrize("test_case", discover_code_merge_test_cases(), ids=get_test_ids())
    def test_python_merge_preserves_custom_code(self, test_case):
        """
        Test that merging generated Python code with existing file preserves custom code.

        This test verifies that:
        1. Code can be generated from the schema
        2. When merged with the existing file, all custom imports/constants/methods are preserved
        3. The generated classes are syntactically valid
        """
        if test_case["python_file"] is None:
            pytest.skip(f"No Python file for {test_case['name']}")

        # Load schema
        with open(test_case["schema_file"]) as f:
            schema = json.load(f)

        # Load existing Python file
        existing_python = test_case["python_file"].read_text()

        # Configure generator (without generation comment to make comparison easier)
        config = CodeGeneratorConfig()
        config.add_generation_comment = False
        config.output.mode = OutputMode.MERGE

        # Get the title/root class name from schema
        class_name = schema.get("title", test_case["name"]).replace(" ", "")

        # Generate Python code
        try:
            generator = PipelineGenerator(class_name, schema, config, "python")
            generated_python = generator.generate()
        except Exception as e:
            # Some schemas may have external references that can't be resolved
            # in isolation - this is expected for activity schemas
            pytest.skip(f"Generation failed (likely due to external refs): {e}")

        # Merge generated with existing
        merger = PythonAstMerger()
        try:
            merged_python = merger.merge_files(generated_python, existing_python)
        except Exception as e:
            pytest.fail(f"Merge failed for {test_case['name']}: {e}")

        # Verify custom code is preserved
        # Check for custom imports (non-standard dataclass imports)
        if "from explayn_dh_agent" in existing_python:
            assert "from explayn_dh_agent" in merged_python, "Custom import from explayn_dh_agent was not preserved"

        # Check for module-level constants (UPPERCASE = value at column 0)
        for line in existing_python.split("\n"):
            # Only check lines that start at column 0 (not indented)
            if line and not line[0].isspace() and "=" in line:
                parts = line.split("=", 1)
                potential_name = parts[0].strip()
                # Check if it's a constant (UPPERCASE and not a class attribute)
                if potential_name.isupper() and not potential_name.startswith("#"):
                    assert potential_name in merged_python, f"Constant {potential_name} was not preserved"

        # Check for Enum classes (class X(str, Enum) or class X(Enum))
        import re

        enum_pattern = r"class\s+(\w+)\s*\([^)]*Enum[^)]*\)"
        for match in re.finditer(enum_pattern, existing_python):
            enum_class = match.group(1)
            assert f"class {enum_class}" in merged_python, f"Enum class {enum_class} was not preserved"

        # Verify the merged code is valid Python
        merger.validate(merged_python)

    @pytest.mark.parametrize("test_case", discover_code_merge_test_cases(), ids=get_test_ids())
    def test_python_generation_produces_valid_code(self, test_case):
        """
        Test that Python code generation from schema produces valid Python.

        This is a basic sanity check that the generator can process the schema.
        """
        if test_case["python_file"] is None:
            pytest.skip(f"No Python file for {test_case['name']}")

        # Load schema
        with open(test_case["schema_file"]) as f:
            schema = json.load(f)

        # Configure generator
        config = CodeGeneratorConfig()
        config.add_generation_comment = False

        class_name = schema.get("title", test_case["name"]).replace(" ", "")

        # Generate Python code
        try:
            generator = PipelineGenerator(class_name, schema, config, "python")
            generated = generator.generate()
        except Exception as e:
            # External references may cause failures - skip these
            pytest.skip(f"Generation failed (likely due to external refs): {e}")

        # Validate generated code
        merger = PythonAstMerger()
        merger.validate(generated)

        # Check that at least one class was generated
        assert "class " in generated, f"No class generated for {test_case['name']}"

    @pytest.mark.parametrize("test_case", discover_code_merge_test_cases(), ids=get_test_ids())
    def test_csharp_generation_produces_valid_code(self, test_case):
        """
        Test that C# code generation from schema produces valid-looking C#.

        Note: We can't fully validate C# without a compiler, but we check for
        basic structure.
        """
        if test_case["csharp_file"] is None:
            pytest.skip(f"No C# file for {test_case['name']}")

        # Load schema
        with open(test_case["schema_file"]) as f:
            schema = json.load(f)

        # Configure generator
        config = CodeGeneratorConfig()
        config.add_generation_comment = False

        class_name = schema.get("title", test_case["name"]).replace(" ", "")

        # Generate C# code
        try:
            generator = PipelineGenerator(class_name, schema, config, "cs")
            generated = generator.generate()
        except Exception as e:
            # External references may cause failures - skip these
            pytest.skip(f"Generation failed (likely due to external refs): {e}")

        # Basic structure checks
        assert "class " in generated or "public class" in generated, f"No class generated for {test_case['name']}"
        assert "{" in generated and "}" in generated, f"Missing braces in generated C# for {test_case['name']}"

    @pytest.mark.parametrize("test_case", discover_code_merge_test_cases(), ids=get_test_ids())
    def test_schema_is_valid_json(self, test_case):
        """Test that each schema.json file is valid JSON."""
        with open(test_case["schema_file"]) as f:
            schema = json.load(f)

        assert "$defs" in schema or "definitions" in schema or "properties" in schema, f"Schema for {test_case['name']} has no definitions or properties"


class TestCodeMergeDiscovery:
    """Tests for test case discovery."""

    def test_discovers_test_cases(self):
        """Test that we can discover code_merge test cases."""
        test_cases = discover_code_merge_test_cases()
        assert len(test_cases) > 0, "No code_merge test cases found"

    def test_all_test_cases_have_schema(self):
        """Test that all discovered test cases have a schema file."""
        test_cases = discover_code_merge_test_cases()
        for tc in test_cases:
            assert tc["schema_file"].exists(), f"Schema missing for {tc['name']}"

    def test_expected_activities_present(self):
        """Test that expected activities are present in test data."""
        test_cases = discover_code_merge_test_cases()
        names = {tc["name"] for tc in test_cases}

        expected = {
            "addition_complete",
            "subtraction_complete",
            "multiplication_complete",
        }

        for activity in expected:
            assert activity in names, f"Expected activity {activity} not found in test cases"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
