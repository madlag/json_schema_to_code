import json
from pathlib import Path
from unittest import TestCase

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


class TestCommentHandling(TestCase):
    """Test that comment fields in schema definitions are properly ignored"""

    def setUp(self):
        self.test_data_path = Path(__file__).parent / "test_data" / "comment_handling_tests.json"
        with open(self.test_data_path) as f:
            self.test_cases = json.load(f)

    def _generate_code(self, schema, config_dict):
        """Helper to generate code with given schema and config"""
        config = CodeGeneratorConfig()
        for key, value in config_dict.items():
            setattr(config, key, value)

        codegen = CodeGenerator("TestSchema", schema, config, "python")
        return codegen.generate()

    def test_schema_with_comments(self):
        """Test that comment fields are ignored and don't cause errors"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "schema_with_comments")

        # This should not raise an exception
        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check comment fields are not treated as classes
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_schema_without_comments(self):
        """Test normal schema processing without comment fields"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "schema_without_comments")

        generated_code = self._generate_code(test_case["schema"], test_case["config"])

        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(
                expected, generated_code, f"Expected '{expected}' not found in generated code"
            )

        # Check no comment artifacts
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(
                not_expected, generated_code, f"Unwanted '{not_expected}' found in generated code"
            )

    def test_all_comment_cases(self):
        """Run all comment handling test cases from test data file"""
        for test_case in self.test_cases:
            with self.subTest(test_case=test_case["name"]):
                # This should not raise any exceptions
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
