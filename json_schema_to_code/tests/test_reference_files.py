import json
from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def discover_test_cases():
    """Automatically discover all test cases from test_cases directory"""
    test_cases_dir = Path(__file__).parent / "test_data" / "test_cases"
    test_cases = []

    # Iterate through each test case directory
    for test_dir in sorted(test_cases_dir.iterdir()):
        if not test_dir.is_dir() or test_dir.name.startswith("."):
            continue

        schema_file = test_dir / "schema.json"
        config_file = test_dir / "config.json"

        # Skip if schema doesn't exist
        if not schema_file.exists():
            continue

        test_case_name = test_dir.name

        # Check for Python reference
        py_ref_file = test_dir / "reference.py"
        if py_ref_file.exists():
            test_cases.append(
                {
                    "test_name": f"{test_case_name}_python",
                    "test_dir": test_dir,
                    "schema_file": schema_file,
                    "config_file": config_file,
                    "test_case_name": test_case_name,
                    "language": "python",
                    "reference_file": py_ref_file,
                }
            )

        # Check for C# reference
        cs_ref_file = test_dir / "reference.cs"
        if cs_ref_file.exists():
            test_cases.append(
                {
                    "test_name": f"{test_case_name}_cs",
                    "test_dir": test_dir,
                    "schema_file": schema_file,
                    "config_file": config_file,
                    "test_case_name": test_case_name,
                    "language": "cs",
                    "reference_file": cs_ref_file,
                }
            )

    return test_cases


@pytest.mark.parametrize("test_case", discover_test_cases(), ids=lambda tc: tc["test_name"])
def test_reference_file_generation(test_case):
    """Test code generation against reference files"""
    # Load schema
    with open(test_case["schema_file"]) as f:
        schema = json.load(f)

    # Load config if it exists, otherwise use defaults
    if test_case["config_file"].exists():
        with open(test_case["config_file"]) as f:
            config_dict = json.load(f)
            config = CodeGeneratorConfig.from_dict(config_dict)
    else:
        config = CodeGeneratorConfig()
        config.use_inline_unions = False
        config.add_generation_comment = True
        config.use_future_annotations = True

    # Generate class name from test case name (convert to PascalCase)
    class_name = "".join(word.capitalize() for word in test_case["test_case_name"].split("_"))

    # Generate code
    codegen = CodeGenerator(class_name, schema, config, test_case["language"])
    generated_code = codegen.generate()

    # Load reference file
    with open(test_case["reference_file"]) as f:
        reference_code = f.read()

    # Compare generated code with reference
    # Normalize line endings for cross-platform compatibility
    generated_normalized = generated_code.replace("\r\n", "\n").strip()
    reference_normalized = reference_code.replace("\r\n", "\n").strip()

    if generated_normalized != reference_normalized:
        # Generate diff for better error messages
        import difflib

        diff = difflib.unified_diff(
            reference_normalized.splitlines(keepends=True),
            generated_normalized.splitlines(keepends=True),
            fromfile="reference",
            tofile="generated",
            lineterm="",
        )
        diff_text = "".join(diff)

        pytest.fail(
            f"Generated code does not match reference for {test_case['test_name']}\n\nDiff:\n{diff_text}"
        )


if __name__ == "__main__":
    # For manual testing - print discovered test cases
    test_cases = discover_test_cases()
    print(f"Discovered {len(test_cases)} test cases:")
    for tc in test_cases:
        print(f"  - {tc['test_name']}")
