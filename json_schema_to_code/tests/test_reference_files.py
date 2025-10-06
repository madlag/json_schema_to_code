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
        language_extensions = {"python": "py", "cs": "cs"}
        for language in ["python", "cs"]:
            # Check if reference file exists
            extension = language_extensions[language]
            ref_file = (
                Path(__file__).parent / "test_data" / "references" / f"{schema_name}.{extension}"
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


@pytest.mark.parametrize("test_case", discover_schema_tests(), ids=lambda tc: tc["test_name"])
def test_reference_file_generation(test_case):
    """Test code generation against reference files"""
    # Load schema
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    # Use default config with inline unions disabled for compatibility
    config = CodeGeneratorConfig()
    config.use_inline_unions = False
    config.add_generation_comment = True
    config.use_future_annotations = True

    # Convert schema file stem to PascalCase for class name
    class_name = "".join(word.capitalize() for word in test_case["schema_name"].split("_"))

    # Generate code
    generator = CodeGenerator(class_name, schema, config, test_case["language"])
    generated_output = generator.generate()

    # Create test output directory and save generated file
    test_output_dir = Path(__file__).parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    language_extensions = {"python": "py", "cs": "cs"}
    extension = language_extensions[test_case["language"]]
    output_file = test_output_dir / f"{test_case['schema_name']}_generated.{extension}"

    with open(output_file, "w") as f:
        f.write(generated_output)

    print(f"Generated file saved to: {output_file}")

    # Load reference file
    with open(test_case["reference_file"]) as f:
        reference_output = f.read()

    # Compare generated output with reference (normalize whitespace)
    # This makes tests more robust to minor formatting differences
    normalized_generated = generated_output.strip()
    normalized_reference = reference_output.strip()

    assert (
        normalized_generated == normalized_reference
    ), f"Generated output doesn't match reference for {test_case['test_name']}\n\nGenerated:\n{repr(generated_output)}\n\nExpected:\n{repr(reference_output)}"


if __name__ == "__main__":
    pytest.main([__file__])
