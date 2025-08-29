import json
from pathlib import Path
from unittest import TestCase

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


class TestUnionTypes(TestCase):
    """Test union type handling with inline unions vs type aliases"""

    def setUp(self):
        self.test_data_path = Path(__file__).parent / "test_data" / "union_types_tests.json"
        with open(self.test_data_path) as f:
            self.test_cases = json.load(f)

    def _generate_code(self, schema, config_dict):
        """Helper to generate code with given schema and config"""
        config = CodeGeneratorConfig()
        for key, value in config_dict.items():
            setattr(config, key, value)

        codegen = CodeGenerator("TestSchema", schema, config, "python")
        return codegen.generate()

    def test_anyof_inline_unions(self):
        """Test anyOf patterns with inline unions enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "anyOf_inline_unions")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_anyof_type_aliases(self):
        """Test anyOf patterns with type aliases enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "anyOf_type_aliases")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_oneof_inline_unions(self):
        """Test oneOf patterns with inline unions enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "oneOf_inline_unions")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_oneof_type_aliases(self):
        """Test oneOf patterns with type aliases enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "oneOf_type_aliases")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_array_type_unions_inline(self):
        """Test array type unions with inline unions enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "array_type_unions_inline")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_array_type_unions_aliases(self):
        """Test array type unions with type aliases enabled"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "array_type_unions_aliases")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_no_unions_no_aliases(self):
        """Test that schemas without unions don't generate type aliases"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "no_unions_no_aliases")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_all_cases_comprehensive(self):
        """Run all test cases from test data file"""
        for test_case in self.test_cases:
            with self.subTest(test_case=test_case["name"]):
                generated_code = self._generate_code(test_case["schema"], test_case["config"])

                # Check expected content is present
                for expected in test_case["expected_contains"]:
                    self.assertIn(
                        expected,
                        generated_code,
                        f"Test '{test_case['name']}': Expected '{expected}' not found",
                    )

                # Check unwanted content is not present
                for not_expected in test_case["expected_not_contains"]:
                    self.assertNotIn(
                        not_expected,
                        generated_code,
                        f"Test '{test_case['name']}': Unwanted '{not_expected}' found",
                    )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
