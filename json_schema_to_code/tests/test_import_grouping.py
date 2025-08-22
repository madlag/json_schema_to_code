import json
import pytest
from pathlib import Path
from ..codegen import CodeGenerator, CodeGeneratorConfig, ImportType

class TestImportGrouping:
    """Test class for import grouping functionality"""
    
    def test_python_import_grouping_basic(self):
        """Test basic Python import grouping from typing module"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "python")
        
        # Register multiple typing imports
        generator.register_import_needed(ImportType.LIST)
        generator.register_import_needed(ImportType.ANY)
        generator.register_import_needed(ImportType.LITERAL)
        
        assembled_imports = generator._assemble_python_imports()
        
        # Should have base imports and grouped typing imports
        expected_base = ["from dataclasses import dataclass", "from dataclasses_json import dataclass_json"]
        expected_typing = "from typing import Any, List, Literal"
        
        for base_import in expected_base:
            assert base_import in assembled_imports
        assert expected_typing in assembled_imports
        
    def test_python_import_grouping_mixed_modules(self):
        """Test Python import grouping with imports from different modules"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "python")
        
        # Register imports from different modules
        generator.register_import_needed(ImportType.LIST)  # typing
        generator.register_import_needed(ImportType.SUB_CLASSES)  # abc
        generator.register_import_needed(ImportType.ENUM)  # enum
        
        assembled_imports = generator._assemble_python_imports()
        
        # Check each module has its own import line
        assert "from abc import ABC" in assembled_imports
        assert "from enum import Enum" in assembled_imports
        assert "from typing import List" in assembled_imports
        
        # Check alphabetical ordering of modules
        abc_index = next(i for i, imp in enumerate(assembled_imports) if "from abc" in imp)
        enum_index = next(i for i, imp in enumerate(assembled_imports) if "from enum" in imp)
        typing_index = next(i for i, imp in enumerate(assembled_imports) if "from typing" in imp)
        
        assert abc_index < enum_index  # abc comes before enum
        
    def test_python_import_deduplication(self):
        """Test that duplicate import registrations don't create duplicates"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "python")
        
        # Register the same import multiple times
        generator.register_import_needed(ImportType.LIST)
        generator.register_import_needed(ImportType.LIST)
        generator.register_import_needed(ImportType.ANY)
        generator.register_import_needed(ImportType.ANY)
        
        assembled_imports = generator._assemble_python_imports()
        
        # Should only have one typing import line with both types
        typing_imports = [imp for imp in assembled_imports if "from typing import" in imp]
        assert len(typing_imports) == 1
        assert "from typing import Any, List" in typing_imports[0]
        
    def test_cs_imports_unchanged(self):
        """Test that C# imports are not affected by Python grouping logic"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "cs")
        
        generator.register_import_needed(ImportType.LIST)
        generator.register_import_needed(ImportType.SUB_CLASSES)
        
        # C# should still use the old system (required_imports set)
        assert "System.Collections.Generic" in generator.required_imports
        assert "JsonSubTypes" in generator.required_imports
        
        # Python assembly method should return empty for C#
        assert generator._assemble_python_imports() == []
        
    def test_template_integration_python(self):
        """Test that Python templates receive properly formatted imports"""
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "data": {"type": "object"}
                    }
                }
            }
        }
        
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", schema, config, "python")
        code = generator.generate()
        
        # Check that imports are properly grouped in the generated code
        assert "from dataclasses import dataclass" in code
        assert "from dataclasses_json import dataclass_json" in code
        assert "from typing import Any, List" in code
        
        # Should not have separate lines for each typing import
        assert "from typing import Any" not in code.replace("from typing import Any, List", "")
        assert "from typing import List" not in code.replace("from typing import Any, List", "")
        
    def test_template_integration_cs(self):
        """Test that C# templates still work correctly"""
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object", 
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        }
        
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", schema, config, "cs")
        code = generator.generate()
        
        # Check that C# imports are present
        assert "using System;" in code
        assert "using Newtonsoft.Json;" in code
        assert "using System.Collections.Generic;" in code
        
    def test_empty_imports(self):
        """Test behavior when no imports are needed"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "python")
        
        # Don't register any additional imports beyond BASE
        assembled_imports = generator._assemble_python_imports()
        
        # Should only have base imports
        assert "from dataclasses import dataclass" in assembled_imports
        assert "from dataclasses_json import dataclass_json" in assembled_imports
        assert len(assembled_imports) == 2
        
    def test_import_sorting_within_module(self):
        """Test that imports within a module are sorted alphabetically"""
        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", {}, config, "python")
        
        # Register imports in non-alphabetical order
        generator.register_import_needed(ImportType.TUPLE)  # Should be last
        generator.register_import_needed(ImportType.ANY)    # Should be first
        generator.register_import_needed(ImportType.LIST)   # Should be middle
        
        assembled_imports = generator._assemble_python_imports()
        
        # Find the typing import line
        typing_line = next(imp for imp in assembled_imports if "from typing import" in imp)
        
        # Should be alphabetically sorted: Any, List, Tuple
        assert "from typing import Any, List, Tuple" == typing_line
    
    def test_future_annotations_import(self):
        """Test that use_future_annotations config adds __future__ import at the top"""
        config = CodeGeneratorConfig()
        config.use_future_annotations = True
        
        # Simple schema to generate code
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }
        
        generator = CodeGenerator("TestSchema", schema, config, "python")
        output = generator.generate()
        
        # Check that __future__ import is present and at the top
        lines = output.split('\n')
        import_lines = [line for line in lines if line.startswith('from ')]
        
        # Should have __future__ import
        assert any("from __future__ import annotations" in line for line in import_lines)
        
        # __future__ import should be first among import lines
        future_import_line = next(i for i, line in enumerate(lines) if "from __future__ import annotations" in line)
        other_import_lines = [i for i, line in enumerate(lines) if line.startswith('from ') and "__future__" not in line]
        
        # Future import should come before all other imports
        if other_import_lines:
            assert future_import_line < min(other_import_lines)
    
    def test_future_annotations_disabled(self):
        """Test that __future__ import is not added when use_future_annotations is False"""
        config = CodeGeneratorConfig()
        config.use_future_annotations = False  # Default value, but explicit for clarity
        
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object", 
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }
        
        generator = CodeGenerator("TestSchema", schema, config, "python")
        output = generator.generate()
        
        # Should not contain __future__ import
        assert "from __future__ import annotations" not in output

if __name__ == "__main__":
    pytest.main([__file__])
