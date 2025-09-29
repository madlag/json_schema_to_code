import json
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def discover_schema_tests():
    """Automatically discover all schemas and create test cases for both languages"""
    schemas_dir = Path(__file__).parent / "test_data" / "schemas"
    test_cases = []

    for schema_file in schemas_dir.glob("*.json"):
        schema_name = schema_file.stem

        # Create test cases for both languages
        for language in ["python", "cs"]:
            # Check if reference file exists
            ref_file = (
                Path(__file__).parent / "test_data" / "references" / f"{schema_name}.{language}"
            )
            if ref_file.exists():
                test_cases.append(
                    {
                        "test_name": f"{schema_name}_{language}",
                        "schema_file": schema_file,
                        "schema_name": schema_name,
                        "language": language,
                        "reference_file": ref_file,
                    }
                )

    return test_cases


@pytest.mark.parametrize("test_case", discover_schema_tests())
def test_reference_file_generation(test_case):
    """Test code generation against reference files"""
    # Load schema
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    # Use default config with inline unions disabled for compatibility
    config = CodeGeneratorConfig()
    config.use_inline_unions = False

    # Determine class name from schema name (match existing reference files)
    schema_name = test_case["schema_name"]
    if schema_name == "dhclient":
        class_name = "dh_client"  # Special case for dhclient
    elif schema_name == "addition_exercise":
        class_name = "AdditionExercise"  # PascalCase for addition exercise
    elif schema_name == "geometry":
        class_name = "geometry"  # Keep lowercase for geometry (matches reference)
    else:
        # Convert snake_case to PascalCase
        class_name = "".join(word.capitalize() for word in schema_name.split("_"))

    # Generate code
    generator = CodeGenerator(class_name, schema, config, test_case["language"])
    generated_output = generator.generate()

    # Load reference file
    with open(test_case["reference_file"]) as f:
        reference_output = f.read()

    # Compare generated output with reference
    assert (
        generated_output == reference_output
    ), f"Generated output doesn't match reference for {test_case['test_name']}"


if __name__ == "__main__":
    pytest.main([__file__])
