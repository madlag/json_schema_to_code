import json
import pytest
from pathlib import Path
from ..codegen import CodeGenerator, CodeGeneratorConfig

def load_test_data():
    """Load test data from JSON file"""
    test_data_path = Path(__file__).parent / "test_data" / "quoted_types_tests.json"
    with open(test_data_path) as f:
        return json.load(f)

class TestQuotedTypes:
    """Test class for quoted types functionality"""
    
    @pytest.mark.parametrize("test_case", load_test_data())
    def test_quoted_types_generation(self, test_case):
        """Test quoted types generation based on test data"""
        name = test_case["name"]
        description = test_case["description"]
        config_data = test_case["config"]
        schema = test_case["schema"]
        expected_contains = test_case["expected_contains"]
        expected_not_contains = test_case["expected_not_contains"]
        
        print(f"\nTesting: {name}")
        print(f"Description: {description}")
        
        # Create configuration
        config = CodeGeneratorConfig.from_dict(config_data)
        
        # Generate code
        generator = CodeGenerator("TestSchema", schema, config, "python")
        generated_code = generator.generate()
        
        print(f"Generated code:\n{generated_code}")
        
        # Check that expected content is present
        for expected in expected_contains:
            assert expected in generated_code, f"Expected '{expected}' to be in generated code for test '{name}'"
        
        # Check that unwanted content is not present
        for not_expected in expected_not_contains:
            assert not_expected not in generated_code, f"Expected '{not_expected}' to NOT be in generated code for test '{name}'"

if __name__ == "__main__":
    pytest.main([__file__])
