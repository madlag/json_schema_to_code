import json
import unittest
from pathlib import Path
from unittest import TestCase

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


class TestUIHierarchy(TestCase):
    """Test UI hierarchy schema - real-world complex schema with multiple advanced features"""
    
    def setUp(self):
        self.test_data_path = Path(__file__).parent / "test_data" / "ui_hierarchy_tests.json"
        with open(self.test_data_path) as f:
            self.test_cases = json.load(f)
    
    def _generate_code(self, schema_file_path, config_dict):
        """Helper to generate code with given schema file and config"""
        # Load schema from file (handle relative paths)
        if not Path(schema_file_path).is_absolute():
            schema_file_path = Path(__file__).parent / schema_file_path
        with open(schema_file_path) as f:
            schema = json.load(f)
            
        config = CodeGeneratorConfig()
        for key, value in config_dict.items():
            setattr(config, key, value)
        
        codegen = CodeGenerator("UIHierarchy", schema, config, "python")
        return codegen.generate()
    
    def _run_test_case(self, test_case_name):
        """Helper to run a specific test case"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == test_case_name)
        
        # Check if schema file exists
        schema_file = test_case["schema_file"]
        if not Path(schema_file).is_absolute():
            schema_path = Path(__file__).parent / schema_file
        else:
            schema_path = Path(schema_file)
        if not schema_path.exists():
            self.skipTest(f"Schema file not found: {schema_path}")
        
        generated_code = self._generate_code(schema_file, test_case["config"])
        
        # Check expected content is present
        for expected in test_case["expected_contains"]:
            self.assertIn(expected, generated_code,
                         f"Expected '{expected}' not found in generated code")
        
        # Check unwanted content is not present
        for not_expected in test_case["expected_not_contains"]:
            self.assertNotIn(not_expected, generated_code,
                           f"Unwanted '{not_expected}' found in generated code")
        
        return generated_code
    
    def test_ui_hierarchy_inline_unions(self):
        """Test UI hierarchy schema with inline unions enabled"""
        self._run_test_case("ui_hierarchy_inline_unions")
    
    def test_ui_hierarchy_type_aliases(self):
        """Test UI hierarchy schema with type aliases enabled"""
        self._run_test_case("ui_hierarchy_type_aliases")
    
    def test_ui_hierarchy_comment_filtering(self):
        """Test that comment fields are properly filtered out"""
        self._run_test_case("ui_hierarchy_comment_filtering")
    
    def test_ui_hierarchy_inheritance(self):
        """Test that inheritance relationships are properly generated"""
        self._run_test_case("ui_hierarchy_inheritance")
    
    def test_all_ui_hierarchy_cases(self):
        """Run all UI hierarchy test cases comprehensively"""
        for test_case in self.test_cases:
            with self.subTest(test_case=test_case["name"]):
                # Check if schema file exists
                schema_file = test_case["schema_file"]
                if not Path(schema_file).is_absolute():
                    schema_path = Path(__file__).parent / schema_file
                else:
                    schema_path = Path(schema_file)
                if not schema_path.exists():
                    self.skipTest(f"Schema file not found: {schema_path}")
                
                generated_code = self._generate_code(schema_file, test_case["config"])
                
                # Check expected content is present
                for expected in test_case["expected_contains"]:
                    self.assertIn(expected, generated_code,
                                 f"Test '{test_case['name']}': Expected '{expected}' not found")
                
                # Check unwanted content is not present
                for not_expected in test_case["expected_not_contains"]:
                    self.assertNotIn(not_expected, generated_code,
                                   f"Test '{test_case['name']}': Unwanted '{not_expected}' found")
    
    def test_ui_hierarchy_comprehensive_generation(self):
        """Test that the UI hierarchy schema generates all expected classes and relationships"""
        test_case = next(tc for tc in self.test_cases if tc["name"] == "ui_hierarchy_inline_unions")
        
        # Check if schema file exists
        schema_file = test_case["schema_file"]
        if not Path(schema_file).is_absolute():
            schema_path = Path(__file__).parent / schema_file
        else:
            schema_path = Path(schema_file)
        if not schema_path.exists():
            self.skipTest(f"Schema file not found: {schema_path}")
        
        generated_code = self._run_test_case("ui_hierarchy_inline_unions")
        
        # Additional comprehensive checks
        expected_classes = [
            "style", "baseUIObject", "textObject", "buttonObject", 
            "inputObject", "imageObject", "containerObject", "listObject",
            "modalObject", "formObject", "tableObject", "uiObjectUnion"
        ]
        
        for class_name in expected_classes:
            self.assertIn(f"class {class_name}", generated_code,
                         f"Expected class '{class_name}' not found in generated code")
        
        # Check that ABC is used for base classes
        self.assertIn("baseUIObject(ABC)", generated_code)
        
        # Check that inheritance is working (derived classes extend base)
        inheritance_patterns = [
            "textObject(baseUIObject)",
            "buttonObject(baseUIObject)", 
            "inputObject(baseUIObject)",
            "containerObject(baseUIObject)"
        ]
        
        for pattern in inheritance_patterns:
            self.assertIn(pattern, generated_code,
                         f"Expected inheritance pattern '{pattern}' not found")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
