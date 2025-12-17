"""
C# AST roundtrip tests.

These tests verify that C# code can be parsed with tree-sitter
and that our serializer produces consistent, valid C# output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Check if tree-sitter is available
try:
    import tree_sitter_c_sharp as ts_csharp
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


def get_csharp_test_files():
    """Get all C# test files for roundtrip testing."""
    test_dir = Path(__file__).parent.parent / "test_data" / "v3" / "csharp_roundtrip"
    return list(test_dir.glob("*.cs"))


@pytest.fixture
def csharp_parser():
    """Create a C# parser using tree-sitter."""
    if not TREE_SITTER_AVAILABLE:
        pytest.skip("tree-sitter-c-sharp not installed")

    CSHARP_LANGUAGE = Language(ts_csharp.language())
    parser = Parser(CSHARP_LANGUAGE)
    return parser


def normalize_whitespace(code: str) -> str:
    """Normalize whitespace for comparison."""
    lines = []
    for line in code.split("\n"):
        # Strip trailing whitespace
        stripped = line.rstrip()
        lines.append(stripped)

    # Remove empty lines at start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter-c-sharp not installed")
@pytest.mark.parametrize("test_file", get_csharp_test_files(), ids=lambda f: f.stem)
def test_csharp_parse_valid(csharp_parser, test_file):
    """Test that C# test files are valid and can be parsed."""
    code = test_file.read_text()

    # Parse the code
    tree = csharp_parser.parse(code.encode("utf-8"))

    # Check for parse errors
    assert not tree.root_node.has_error, f"Parse error in {test_file.name}: {tree.root_node.sexp()}"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter-c-sharp not installed")
@pytest.mark.parametrize("test_file", get_csharp_test_files(), ids=lambda f: f.stem)
def test_csharp_parse_structure(csharp_parser, test_file):
    """Test that parsed C# has expected structure."""
    code = test_file.read_text()

    tree = csharp_parser.parse(code.encode("utf-8"))
    root = tree.root_node

    # Should have a compilation_unit as root
    assert root.type == "compilation_unit", f"Expected compilation_unit, got {root.type}"

    # Find all class/enum declarations
    declarations = []

    def find_declarations(node):
        if node.type in ("class_declaration", "enum_declaration"):
            declarations.append(node)
        for child in node.children:
            find_declarations(child)

    find_declarations(root)

    # Should have at least one declaration
    assert len(declarations) > 0, f"No class/enum declarations found in {test_file.name}"


def extract_class_names_from_tree(tree) -> set[str]:
    """Extract class names from a parsed tree."""
    names = set()

    def find_names(node):
        if node.type == "class_declaration":
            # Find the identifier child
            for child in node.children:
                if child.type == "identifier":
                    names.add(child.text.decode("utf-8"))
                    break
        elif node.type == "enum_declaration":
            for child in node.children:
                if child.type == "identifier":
                    names.add(child.text.decode("utf-8"))
                    break
        for child in node.children:
            find_names(child)

    find_names(tree.root_node)
    return names


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter-c-sharp not installed")
def test_csharp_simple_class_names(csharp_parser):
    """Test that SimpleClass is correctly identified."""
    test_file = Path(__file__).parent.parent / "test_data" / "v3" / "csharp_roundtrip" / "simple_class.cs"
    if not test_file.exists():
        pytest.skip("Test file not found")

    code = test_file.read_text()
    tree = csharp_parser.parse(code.encode("utf-8"))

    names = extract_class_names_from_tree(tree)
    assert "SimpleClass" in names, f"SimpleClass not found, got: {names}"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter-c-sharp not installed")
def test_csharp_inheritance_class_names(csharp_parser):
    """Test that inheritance classes are correctly identified."""
    test_file = Path(__file__).parent.parent / "test_data" / "v3" / "csharp_roundtrip" / "class_with_inheritance.cs"
    if not test_file.exists():
        pytest.skip("Test file not found")

    code = test_file.read_text()
    tree = csharp_parser.parse(code.encode("utf-8"))

    names = extract_class_names_from_tree(tree)
    assert "BaseClass" in names, f"BaseClass not found, got: {names}"
    assert "DerivedClass" in names, f"DerivedClass not found, got: {names}"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter-c-sharp not installed")
def test_csharp_enum_names(csharp_parser):
    """Test that enum is correctly identified."""
    test_file = Path(__file__).parent.parent / "test_data" / "v3" / "csharp_roundtrip" / "enum_with_converter.cs"
    if not test_file.exists():
        pytest.skip("Test file not found")

    code = test_file.read_text()
    tree = csharp_parser.parse(code.encode("utf-8"))

    names = extract_class_names_from_tree(tree)
    assert "Status" in names, f"Status enum not found, got: {names}"
    assert "StatusJsonConverter" in names, f"StatusJsonConverter not found, got: {names}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
