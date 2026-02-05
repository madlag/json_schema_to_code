"""
Tests for the V3 pipeline merge functionality.

Tests the AST-level merging of generated code with existing files,
including preservation of custom imports, methods, and __post_init__.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, MergeStrategy, OutputMode, PipelineGenerator
from json_schema_to_code.pipeline.merger import (
    AtomicWriter,
    CodeMergeError,
    PythonAstMerger,
)

# Test schema for generating code
SIMPLE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        "Person": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
    },
}


class TestPythonAstMerger:
    """Tests for PythonAstMerger."""

    def test_parse_valid_python(self):
        """Test parsing valid Python code."""
        merger = PythonAstMerger()
        code = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int = 0
"""
        tree = merger.parse(code)
        assert tree is not None

    def test_parse_invalid_python_raises_error(self):
        """Test that invalid Python raises CodeMergeError."""
        merger = PythonAstMerger()
        code = "class Broken("  # Invalid syntax

        with pytest.raises(CodeMergeError):
            merger.parse(code)

    @pytest.mark.skip(reason="extract_custom_code replaced by order-preserving merge_files")
    def test_extract_custom_imports(self):
        """Test extraction of custom import statements."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import json
from my_custom_module import helper

@dataclass_json
@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass
class Person:
    name: str
"""

        custom = merger.extract_custom_code(existing, generated)

        # Should find the custom import
        assert len(custom.custom_imports) == 2
        assert any("json" in imp for imp in custom.custom_imports)
        assert any("my_custom_module" in imp for imp in custom.custom_imports)

    @pytest.mark.skip(reason="extract_custom_code replaced by order-preserving merge_files")
    def test_extract_custom_constants(self):
        """Test extraction of module-level constants."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

MY_CONSTANT = 42
DEFAULT_NAME = "Unknown"

@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""

        custom = merger.extract_custom_code(existing, generated)

        # Should find both constants
        assert len(custom.constants) == 2
        assert any("MY_CONSTANT" in c for c in custom.constants)
        assert any("DEFAULT_NAME" in c for c in custom.constants)

    @pytest.mark.skip(reason="extract_custom_code replaced by order-preserving merge_files")
    def test_extract_custom_methods(self):
        """Test extraction of custom methods from classes."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str

    def greet(self):
        return f"Hello, {self.name}!"

    def custom_method(self):
        pass
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""

        custom = merger.extract_custom_code(existing, generated)

        # Should find both custom methods
        assert "Person" in custom.class_methods
        assert len(custom.class_methods["Person"]) == 2
        assert any("greet" in m for m in custom.class_methods["Person"])
        assert any("custom_method" in m for m in custom.class_methods["Person"])

    @pytest.mark.skip(reason="extract_custom_code replaced by order-preserving merge_files")
    def test_extract_custom_post_init_body(self):
        """Test extraction of custom __post_init__ body."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str

    def __post_init__(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Name cannot be empty")
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""

        custom = merger.extract_custom_code(existing, generated)

        # Should find custom __post_init__ body
        assert "Person" in custom.post_init_bodies
        assert len(custom.post_init_bodies["Person"]) == 2

    def test_merge_preserves_custom_imports(self):
        """Test that merge preserves custom imports."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass
import json

@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int = 0
"""

        merged = merger.merge_files(generated, existing)

        # Should have the custom import
        assert "import json" in merged
        # Should have the new field
        assert "age: int" in merged

    def test_merge_consolidates_duplicate_imports_from_same_module(self):
        """Test that merge consolidates duplicate imports from the same module."""
        merger = PythonAstMerger()

        # Existing file has duplicate imports from same module (a common issue)
        existing = """
from __future__ import annotations
from dataclasses import dataclass
from mymodule import A, B, C
from other import X
from mymodule import A, B, C, D

@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass
from mymodule import A, B, E

@dataclass
class Person:
    name: str
    age: int = 0
"""

        merged = merger.merge_files(generated, existing)

        # Should consolidate into single import with all names
        import_count = merged.count("from mymodule import")
        assert import_count == 1, f"Expected 1 import from mymodule, got {import_count}"

        # Should have all unique names from both imports
        assert "A" in merged
        assert "B" in merged
        assert "C" in merged
        assert "D" in merged
        assert "E" in merged

    def test_merge_preserves_custom_methods(self):
        """Test that merge preserves custom methods."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str

    def greet(self):
        return f"Hello, {self.name}!"
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int = 0
"""

        merged = merger.merge_files(generated, existing)

        # Should have the custom method
        assert "def greet(self):" in merged
        # Should have the new field
        assert "age: int" in merged

    def test_merge_raises_when_existing_value_member_missing_in_generated(self):
        """Test that merge fails when existing class has a removed value member."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    legacy_value: int = 7
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""

        with pytest.raises(CodeMergeError, match="legacy_value"):
            merger.merge_files(generated, existing)

    def test_merge_strategy_merge_keeps_removed_value_members(self):
        merger = PythonAstMerger()
        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    legacy_value: int = 7
"""
        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""
        merged = merger.merge_files(generated, existing, MergeStrategy.MERGE)
        assert "legacy_value" in merged

    def test_merge_strategy_delete_removes_extra_value_members(self):
        merger = PythonAstMerger()
        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    legacy_value: int = 7
"""
        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""
        merged = merger.merge_files(generated, existing, MergeStrategy.DELETE)
        assert "legacy_value" not in merged
        assert "name: str" in merged

    def test_merge_empty_custom_code_returns_generated(self):
        """Test that merge with no custom code returns generated as-is."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int = 0
"""

        merged = merger.merge_files(generated, existing)

        # Should be the same as generated (no custom code to preserve)
        assert "age: int" in merged

    def test_merge_preserves_custom_classes(self):
        """Test that merge preserves custom class definitions (e.g., Enums)."""
        merger = PythonAstMerger()

        existing = """
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ColorFlag(str, Enum):
    NORMAL = "normal"
    ERROR = "error"

@dataclass
class Person:
    name: str
"""

        generated = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int = 0
"""

        merged = merger.merge_files(generated, existing)

        # Should preserve the custom Enum class
        assert "class ColorFlag" in merged
        assert "NORMAL" in merged
        assert "ERROR" in merged
        # Should have the generated field
        assert "age: int" in merged

    def test_validate_valid_code(self):
        """Test validation passes for valid code."""
        merger = PythonAstMerger()
        code = """
from __future__ import annotations

class Person:
    pass
"""
        # Should not raise
        merger.validate(code)

    def test_validate_invalid_code_raises(self):
        """Test validation fails for invalid code."""
        merger = PythonAstMerger()
        code = "class Broken("

        with pytest.raises(CodeMergeError):
            merger.validate(code)


class TestAtomicWriter:
    """Tests for AtomicWriter."""

    def test_write_creates_file(self):
        """Test that write creates a new file."""
        writer = AtomicWriter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"
            code = """
from __future__ import annotations

class Person:
    pass
"""
            writer.write(path, code, "python")

            assert path.exists()
            assert path.read_text() == code

    def test_write_if_not_exists_raises_on_existing(self):
        """Test that write_if_not_exists raises if file exists."""
        writer = AtomicWriter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing.py"
            path.write_text("existing content")

            with pytest.raises(FileExistsError):
                writer.write_if_not_exists(path, "new content", "python", validate=False)

    def test_write_overwrites_existing(self):
        """Test that write overwrites existing file."""
        writer = AtomicWriter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing.py"
            path.write_text("old content")

            new_code = """
from __future__ import annotations

class NewClass:
    pass
"""
            writer.write(path, new_code, "python")

            assert path.read_text() == new_code

    def test_write_validates_python(self):
        """Test that write validates Python code."""
        writer = AtomicWriter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"
            invalid_code = "class Broken("

            with pytest.raises(CodeMergeError):
                writer.write(path, invalid_code, "python", validate=True)

            # File should not exist after failed write
            assert not path.exists()

    def test_write_without_validation(self):
        """Test that write works without validation."""
        writer = AtomicWriter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"
            # This is technically invalid Python
            code = "not really python code"

            writer.write(path, code, "python", validate=False)

            assert path.exists()
            assert path.read_text() == code


class TestGeneratorMerge:
    """Tests for PipelineGenerator merge functionality."""

    def test_generate_to_file_error_if_exists(self):
        """Test that default mode raises error if file exists."""
        config = CodeGeneratorConfig()
        config.output.mode = OutputMode.ERROR_IF_EXISTS
        config.add_generation_comment = False

        gen = PipelineGenerator("Test", SIMPLE_SCHEMA, config, "python")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"
            path.write_text("existing content")

            with pytest.raises(FileExistsError):
                gen.generate_to_file(path)

    def test_generate_to_file_force_overwrites(self):
        """Test that force mode overwrites existing file."""
        config = CodeGeneratorConfig()
        config.output.mode = OutputMode.FORCE
        config.add_generation_comment = False

        gen = PipelineGenerator("Test", SIMPLE_SCHEMA, config, "python")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"
            path.write_text("old content")

            gen.generate_to_file(path)

            content = path.read_text()
            assert "class Person:" in content

    def test_generate_to_file_creates_new(self):
        """Test that generate_to_file creates new file when none exists."""
        config = CodeGeneratorConfig()
        config.output.mode = OutputMode.ERROR_IF_EXISTS
        config.add_generation_comment = False

        gen = PipelineGenerator("Test", SIMPLE_SCHEMA, config, "python")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"

            gen.generate_to_file(path)

            assert path.exists()
            content = path.read_text()
            assert "class Person:" in content

    def test_generate_to_file_merge_preserves_custom(self):
        """Test that merge mode preserves custom code."""
        config = CodeGeneratorConfig()
        config.output.mode = OutputMode.MERGE
        config.add_generation_comment = False

        gen = PipelineGenerator("Test", SIMPLE_SCHEMA, config, "python")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.py"

            # Create existing file with custom code
            existing = """
from __future__ import annotations
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import json

MY_CONSTANT = 42

@dataclass_json
@dataclass(kw_only=True)
class Person:
    name: str

    def custom_method(self):
        return json.dumps({"name": self.name})
"""
            path.write_text(existing)

            gen.generate_to_file(path)

            content = path.read_text()
            # Should preserve custom import
            assert "import json" in content
            # Should preserve constant
            assert "MY_CONSTANT" in content
            # Should preserve custom method
            assert "custom_method" in content
            # Should have generated field
            assert "age" in content or "name" in content


class TestCSharpMerger:
    """Tests for CSharpAstMerger."""

    def test_csharp_merger_requires_tree_sitter(self):
        """Test that C# merger checks for tree-sitter availability."""
        try:
            from json_schema_to_code.pipeline.merger import CSharpAstMerger

            # If we get here, tree-sitter is available
            merger = CSharpAstMerger()
            assert merger is not None
        except CodeMergeError as e:
            # Expected if tree-sitter not installed
            assert "tree-sitter" in str(e)
        except ImportError:
            # Also acceptable if the import itself fails
            pytest.skip("tree-sitter-c-sharp not installed")

    def test_csharp_merge_does_not_duplicate_properties(self):
        """Regression: merging with corrupted file (duplicate property) must not preserve duplicate."""
        try:
            from json_schema_to_code.pipeline.merger import CSharpAstMerger
        except (CodeMergeError, ImportError):
            pytest.skip("tree-sitter-c-sharp not installed")

        merger = CSharpAstMerger()

        generated = """
using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Test {
    public class UIAction {
        [JsonProperty("operations")]
        public List<object> Operations { get; set; }
        [JsonProperty("metadata")]
        public object Metadata { get; set; }
    }
}
"""

        # Existing file corrupted by previous bad merge - has duplicate Metadata
        existing = """
using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Test {
    public class UIAction {
        [JsonProperty("operations")]
        public List<object> Operations { get; set; }
        [JsonProperty("metadata")]
        public object Metadata { get; set; }

    [JsonProperty("metadata")]
            public object Metadata { get; set; }
    }
}
"""

        merged = merger.merge_files(generated, existing)

        # Must have exactly one Metadata property, not two
        metadata_count = merged.count("public object Metadata { get; set; }")
        assert metadata_count == 1, f"Expected 1 Metadata property, got {metadata_count}"

    def test_csharp_merge_raises_when_existing_value_member_missing_in_generated(self):
        """Test that C# merge fails when existing class has removed property."""
        try:
            from json_schema_to_code.pipeline.merger import CSharpAstMerger
        except (CodeMergeError, ImportError):
            pytest.skip("tree-sitter-c-sharp not installed")

        merger = CSharpAstMerger()

        generated = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }
    }
}
"""

        existing = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("legacy_value")]
        public int LegacyValue { get; set; }
    }
}
"""

        with pytest.raises(CodeMergeError, match="LegacyValue"):
            merger.merge_files(generated, existing)

    def test_csharp_merge_strategy_merge_keeps_removed_property(self):
        try:
            from json_schema_to_code.pipeline.merger import CSharpAstMerger
        except (CodeMergeError, ImportError):
            pytest.skip("tree-sitter-c-sharp not installed")

        merger = CSharpAstMerger()
        generated = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }
    }
}
"""
        existing = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("legacy_value")]
        public int LegacyValue { get; set; }
    }
}
"""
        merged = merger.merge_files(generated, existing, MergeStrategy.MERGE)
        assert "LegacyValue" in merged

    def test_csharp_merge_strategy_delete_removes_extra_property(self):
        try:
            from json_schema_to_code.pipeline.merger import CSharpAstMerger
        except (CodeMergeError, ImportError):
            pytest.skip("tree-sitter-c-sharp not installed")

        merger = CSharpAstMerger()
        generated = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }
    }
}
"""
        existing = """
using System;
using Newtonsoft.Json;

namespace Test {
    public class Person {
        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("legacy_value")]
        public int LegacyValue { get; set; }
    }
}
"""
        merged = merger.merge_files(generated, existing, MergeStrategy.DELETE)
        assert "LegacyValue" not in merged
        assert "Name" in merged


if __name__ == "__main__":
    pytest.main([__file__])
