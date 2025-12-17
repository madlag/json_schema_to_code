from pathlib import Path

import pytest

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


class TestTemplateSimplification:
    """Test class for template simplification functionality"""

    def test_python_template_structure(self):
        """Test that Python template has the same simple structure as C#"""
        # Read both templates
        template_dir = Path(__file__).parent.parent.parent / "templates"

        python_template = (template_dir / "python" / "prefix.py.jinja2").read_text()
        cs_template = (template_dir / "cs" / "prefix.cs.jinja2").read_text()

        # Both should have the same basic loop structure
        assert "{% for import in required_imports %}" in python_template
        assert "{% for import in required_imports %}" in cs_template

        # Python template should be simple without complex conditionals
        assert "{% if import in [" not in python_template  # No hardcoded import lists
        assert "{% set typing_imports" not in python_template  # No complex grouping logic

    def test_python_template_generates_clean_imports(self):
        """Test that Python template generates clean, grouped imports"""
        schema = {
            "definitions": {
                "ComplexClass": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "data": {"type": "object"},
                        "type": {"const": "complex"},
                    },
                }
            }
        }

        config = CodeGeneratorConfig()
        generator = CodeGenerator("ComplexSchema", schema, config, "python")
        code = generator.generate()

        lines = code.split("\n")
        import_lines = [line for line in lines if line.startswith("from ")]

        # Should have clean, separate import lines
        assert len(import_lines) >= 3  # At least dataclasses, dataclasses_json, typing

        # Each import line should be properly formatted
        for import_line in import_lines:
            assert import_line.startswith("from ")
            assert " import " in import_line

        # Typing imports should be grouped
        typing_lines = [line for line in import_lines if "from typing import" in line]
        assert len(typing_lines) == 1  # Should be grouped into one line

    def test_cs_template_unchanged(self):
        """Test that C# template behavior is unchanged"""
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object",
                    "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                }
            }
        }

        config = CodeGeneratorConfig()
        generator = CodeGenerator("TestSchema", schema, config, "cs")
        code = generator.generate()

        lines = code.split("\n")
        using_lines = [line for line in lines if line.startswith("using ")]

        # Should have clean using statements
        expected_usings = [
            "using Newtonsoft.Json;",
            "using System;",
            "using System.Collections.Generic;",
        ]

        for expected in expected_usings:
            assert expected in using_lines

    def test_template_consistency_between_languages(self):
        """Test that both templates follow the same pattern"""
        template_dir = Path(__file__).parent.parent.parent / "templates"

        python_template = (template_dir / "python" / "prefix.py.jinja2").read_text()
        cs_template = (template_dir / "cs" / "prefix.cs.jinja2").read_text()

        # Both should use the same loop variable name
        assert "{% for import in required_imports %}" in python_template
        assert "{% for import in required_imports %}" in cs_template

        # Both should render the import variable directly
        assert "{{ import }}" in python_template
        assert "{{ import }}" in cs_template

    def test_no_unused_template_variables(self):
        """Test that templates don't reference unused variables"""
        template_dir = Path(__file__).parent.parent.parent / "templates"
        python_template = (template_dir / "python" / "prefix.py.jinja2").read_text()

        # Should not reference old complex variables
        assert "typing_imports" not in python_template
        assert "{% if 'Enum'" not in python_template
        assert "{% if 'ABC'" not in python_template

    def test_template_maintains_functionality(self):
        """Test that simplified template maintains all functionality"""
        # Test various scenarios that previously worked
        test_schemas = [
            # Basic schema
            {"definitions": {"Simple": {"type": "object", "properties": {"name": {"type": "string"}}}}},
            # Schema with arrays
            {
                "definitions": {
                    "WithArrays": {
                        "type": "object",
                        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                    }
                }
            },
            # Schema with inheritance (would need SUB_CLASSES)
            {
                "definitions": {
                    "Base": {"type": "object", "properties": {"id": {"type": "string"}}},
                    "Child": {
                        "allOf": [
                            {"$ref": "#/definitions/Base"},
                            {"properties": {"name": {"type": "string"}}},
                        ]
                    },
                }
            },
        ]

        config = CodeGeneratorConfig()

        for i, schema in enumerate(test_schemas):
            generator = CodeGenerator(f"TestSchema{i}", schema, config, "python")
            code = generator.generate()

            # All should generate valid code with proper imports
            assert "from dataclasses import dataclass" in code
            assert "from dataclasses_json import dataclass_json" in code
            assert "@dataclass_json" in code
            assert "@dataclass(kw_only=True)" in code

    def test_import_order_consistency(self):
        """Test that imports are in consistent order"""
        schema = {
            "definitions": {
                "TestClass": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "data": {"type": "object"},
                    },
                }
            }
        }

        config = CodeGeneratorConfig()

        # Generate multiple times to ensure consistency
        codes = []
        for _ in range(3):
            generator = CodeGenerator("TestSchema", schema, config, "python")
            codes.append(generator.generate())

        # All should have the same import order
        import_sections = []
        for code in codes:
            lines = code.split("\n")
            imports = [line for line in lines if line.startswith("from ")]
            import_sections.append(imports)

        # All import sections should be identical
        for import_section in import_sections[1:]:
            assert import_section == import_sections[0]


if __name__ == "__main__":
    pytest.main([__file__])
