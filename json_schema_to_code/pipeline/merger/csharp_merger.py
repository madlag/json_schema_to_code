"""
C# AST merger implementation.

Uses tree-sitter and tree-sitter-c-sharp to parse, extract custom code,
and merge generated code with existing files.
"""

from __future__ import annotations

from typing import Any

from ..config import MergeStrategy
from .base import AstMerger, CodeMergeError, CustomCode

# Try to import tree-sitter
try:
    import tree_sitter_c_sharp as ts_csharp
    from tree_sitter import Language, Node, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None
    Node = None


class CSharpAstMerger(AstMerger):
    """Merger for C# source files using tree-sitter.

    Requires tree-sitter and tree-sitter-c-sharp packages.
    Falls back to text-based merging if not available.
    """

    # Standard using statements that are always generated
    STANDARD_USINGS = {
        "System",
        "System.Collections.Generic",
        "Newtonsoft.Json",
        "JsonSubTypes",
    }

    # Custom code marker comments
    CUSTOM_CODE_START = "// CUSTOM CODE START"
    CUSTOM_CODE_END = "// CUSTOM CODE END"

    def __init__(self):
        """Initialize the C# merger.

        Raises:
            CodeMergeError: If tree-sitter is not available
        """
        if not TREE_SITTER_AVAILABLE:
            raise CodeMergeError("tree-sitter and tree-sitter-c-sharp are required for C# merging. Install with: pip install tree-sitter tree-sitter-c-sharp")

        self._parser = Parser(Language(ts_csharp.language()))

    def parse(self, code: str) -> Any:
        """Parse C# source code into a tree-sitter tree.

        Args:
            code: C# source code string

        Returns:
            tree-sitter Tree object

        Raises:
            CodeMergeError: If the code cannot be parsed
        """
        tree = self._parser.parse(bytes(code, "utf8"))

        # Check for parse errors
        if tree.root_node.has_error:
            # Find the error location
            errors = self._find_errors(tree.root_node)
            if errors:
                first_error = errors[0]
                raise CodeMergeError(f"Failed to parse C# code at line {first_error.start_point[0] + 1}: syntax error near '{first_error.text.decode('utf8')[:50]}...'")

        return tree

    def merge_files(
        self,
        generated_code: str,
        existing_code: str,
        merge_strategy: MergeStrategy = MergeStrategy.ERROR,
    ) -> str:
        custom_code = self._extract_custom_code_with_strategy(existing_code, generated_code, merge_strategy)
        if custom_code.is_empty():
            return generated_code
        merged = self.merge(generated_code, custom_code)
        self.validate(merged)
        return merged

    def extract_custom_code(self, existing_code: str, generated_code: str) -> CustomCode:
        return self._extract_custom_code_with_strategy(existing_code, generated_code, MergeStrategy.ERROR)

    def _extract_custom_code_with_strategy(
        self,
        existing_code: str,
        generated_code: str,
        merge_strategy: MergeStrategy,
    ) -> CustomCode:
        existing_tree = self.parse(existing_code)
        generated_tree = self.parse(generated_code)

        custom = CustomCode()

        # Get generated using statements
        generated_usings = self._extract_usings(generated_tree.root_node, generated_code)

        # Get generated class/enum names
        generated_types = self._extract_type_names(generated_tree.root_node, generated_code)

        # Get generated member names per class
        generated_members = self._extract_class_members(generated_tree.root_node, generated_code)
        generated_value_members = self._extract_class_value_members(generated_tree.root_node, generated_code)

        # Process existing file
        root = existing_tree.root_node

        # Get the file's own namespace to avoid preserving self-imports
        file_namespace = self._extract_file_namespace(generated_tree.root_node, generated_code)

        # Extract custom using statements
        for using in self._find_nodes(root, "using_directive"):
            using_text = self._get_node_text(using, existing_code)
            namespace = self._extract_namespace_from_using(using_text)
            # Skip if: in generated usings, in standard usings, or is the file's own namespace
            if namespace and namespace not in generated_usings and namespace not in self.STANDARD_USINGS:
                if file_namespace and namespace == file_namespace:
                    continue  # Skip self-imports
                custom.custom_imports.append(using_text)

        # Extract custom code from classes
        for class_node in self._find_nodes(root, "class_declaration"):
            class_name = self._get_class_name(class_node, existing_code)
            if not class_name or class_name not in generated_types:
                continue

            gen_members = generated_members.get(class_name, set())

            # Find class body
            body = None
            for child in class_node.children:
                if child.type == "declaration_list":
                    body = child
                    break

            if not body:
                continue

            existing_value_members = self._extract_value_members_from_class_body(body, existing_code)
            generated_value_names = generated_value_members.get(class_name, set())
            for member_name, member_node in existing_value_members.items():
                if member_name in generated_value_names:
                    continue
                if merge_strategy == MergeStrategy.ERROR:
                    line = member_node.start_point[0] + 1
                    column = member_node.start_point[1] + 1
                    raise CodeMergeError(
                        "Merge aborted: existing value member is not generated anymore. "
                        "Use --merge-strategy merge to keep it, "
                        "or --merge-strategy delete to remove it. "
                        f"Location: class '{class_name}', member '{member_name}' "
                        f"at line {line}, column {column}."
                    )

            for member in body.children:
                if member.type == "method_declaration":
                    method_name = self._get_method_name(member, existing_code)
                    if method_name and method_name not in gen_members:
                        if class_name not in custom.class_methods:
                            custom.class_methods[class_name] = []
                        custom.class_methods[class_name].append(self._get_node_text(member, existing_code))

                elif member.type == "property_declaration":
                    prop_name = self._get_property_name(member, existing_code)
                    if prop_name and prop_name not in gen_members:
                        if merge_strategy == MergeStrategy.DELETE:
                            continue
                        if class_name not in custom.class_attributes:
                            custom.class_attributes[class_name] = []
                        custom.class_attributes[class_name].append(self._get_node_text(member, existing_code))

        # Extract custom code sections marked with comments
        custom.raw_sections = self._extract_marked_sections(existing_code)

        return custom

    def merge(self, generated_code: str, custom_code: CustomCode) -> str:
        """Merge custom code into generated C# code.

        Args:
            generated_code: The newly generated code
            custom_code: Custom code elements to preserve

        Returns:
            Merged code string

        Raises:
            CodeMergeError: If merge fails
        """
        lines = generated_code.split("\n")
        result_lines = []

        # Track where we've inserted custom code
        usings_added = False
        current_class = None
        class_end_indices: dict[str, int] = {}

        # First pass: identify class boundaries and generated members
        tree = self.parse(generated_code)
        generated_members = self._extract_class_members(tree.root_node, generated_code)
        for class_node in self._find_nodes(tree.root_node, "class_declaration"):
            class_name = self._get_class_name(class_node, generated_code)
            if class_name:
                # Find the closing brace line
                end_line = class_node.end_point[0]
                class_end_indices[class_name] = end_line

        # Second pass: merge
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Add custom using statements after standard usings
            if stripped.startswith("using ") and not usings_added:
                result_lines.append(line)
                # Check if next line is not a using
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith("using "):
                    for custom_using in custom_code.custom_imports:
                        result_lines.append(custom_using)
                    usings_added = True
                continue

            # Track namespace entry
            if stripped.startswith("namespace "):
                pass

            # Track class entry
            if "class " in stripped and stripped.endswith("{") or ("class " in stripped and i + 1 < len(lines) and lines[i + 1].strip() == "{"):
                # Extract class name
                for class_name in class_end_indices:
                    if f"class {class_name}" in stripped:
                        current_class = class_name
                        break

            # Add custom methods/properties before class closing brace
            if current_class and current_class in class_end_indices:
                if i == class_end_indices[current_class]:
                    # Insert custom members before closing brace
                    indent = "    "  # 4 spaces for class members
                    gen_members = generated_members.get(current_class, set())

                    if current_class in custom_code.class_attributes:
                        for attr in custom_code.class_attributes[current_class]:
                            # Safeguard: skip if this would duplicate a generated property
                            attr_prop_name = self._get_property_name_from_source(attr)
                            if attr_prop_name and attr_prop_name in gen_members:
                                continue
                            result_lines.append("")
                            for attr_line in attr.split("\n"):
                                result_lines.append(indent + attr_line)

                    if current_class in custom_code.class_methods:
                        for method in custom_code.class_methods[current_class]:
                            result_lines.append("")
                            for method_line in method.split("\n"):
                                result_lines.append(indent + method_line)

                    current_class = None

            result_lines.append(line)

        # Add any raw custom sections at the end (before final closing brace)
        if custom_code.raw_sections:
            # Find last closing brace (namespace end)
            for i in range(len(result_lines) - 1, -1, -1):
                if result_lines[i].strip() == "}":
                    # Insert before this
                    for section in custom_code.raw_sections:
                        result_lines.insert(i, "")
                        for section_line in section.split("\n"):
                            result_lines.insert(i, "    " + section_line)
                    break

        return "\n".join(result_lines)

    def validate(self, code: str) -> None:
        """Validate that merged C# code is syntactically correct.

        Args:
            code: The merged code to validate

        Raises:
            CodeMergeError: If validation fails
        """
        self.parse(code)

        # Check for basic structure
        if "namespace " not in code:
            raise CodeMergeError("Merged C# code is missing namespace declaration")

        if "class " not in code and "enum " not in code:
            raise CodeMergeError("Merged C# code has no type definitions")

    def _find_errors(self, node: Any) -> list[Any]:
        """Find all ERROR nodes in the tree."""
        errors = []
        if node.type == "ERROR":
            errors.append(node)
        for child in node.children:
            errors.extend(self._find_errors(child))
        return errors

    def _find_nodes(self, node: Any, node_type: str) -> list[Any]:
        """Find all nodes of a given type in the tree."""
        results = []
        if node.type == node_type:
            results.append(node)
        for child in node.children:
            results.extend(self._find_nodes(child, node_type))
        return results

    def _get_node_text(self, node: Any, code: str) -> str:
        """Get the source text for a node."""
        return code[node.start_byte : node.end_byte]

    def _extract_usings(self, root: Any, code: str) -> set[str]:
        """Extract using statement namespaces."""
        usings = set()
        for using in self._find_nodes(root, "using_directive"):
            text = self._get_node_text(using, code)
            namespace = self._extract_namespace_from_using(text)
            if namespace:
                usings.add(namespace)
        return usings

    def _extract_file_namespace(self, root: Any, code: str) -> str | None:
        """Extract the file's namespace from namespace_declaration."""
        for ns_node in self._find_nodes(root, "namespace_declaration"):
            for child in ns_node.children:
                if child.type == "identifier":
                    return self._get_node_text(child, code)
                # Handle qualified names like "EduObject.Maths.BasicOperations"
                if child.type == "qualified_name":
                    return self._get_node_text(child, code)
        # Try file_scoped_namespace_declaration for C# 10+ style
        for ns_node in self._find_nodes(root, "file_scoped_namespace_declaration"):
            for child in ns_node.children:
                if child.type == "identifier":
                    return self._get_node_text(child, code)
                if child.type == "qualified_name":
                    return self._get_node_text(child, code)
        return None

    def _extract_namespace_from_using(self, using_text: str) -> str | None:
        """Extract namespace from using statement."""
        # "using System.Collections.Generic;" -> "System.Collections.Generic"
        text = using_text.strip()
        if text.startswith("using ") and text.endswith(";"):
            return text[6:-1].strip()
        return None

    def _extract_type_names(self, root: Any, code: str) -> set[str]:
        """Extract class and enum names."""
        names = set()
        for node in self._find_nodes(root, "class_declaration"):
            name = self._get_class_name(node, code)
            if name:
                names.add(name)
        for node in self._find_nodes(root, "enum_declaration"):
            name = self._get_enum_name(node, code)
            if name:
                names.add(name)
        return names

    def _extract_class_members(self, root: Any, code: str) -> dict[str, set[str]]:
        """Extract member names for each class."""
        members = {}
        for class_node in self._find_nodes(root, "class_declaration"):
            class_name = self._get_class_name(class_node, code)
            if not class_name:
                continue

            class_members = set()

            for child in class_node.children:
                if child.type == "declaration_list":
                    for member in child.children:
                        if member.type == "property_declaration":
                            prop_name = self._get_property_name(member, code)
                            if prop_name:
                                class_members.add(prop_name)
                        elif member.type == "method_declaration":
                            method_name = self._get_method_name(member, code)
                            if method_name:
                                class_members.add(method_name)
                        elif member.type == "constructor_declaration":
                            class_members.add(class_name)  # Constructor

            members[class_name] = class_members

        return members

    def _extract_class_value_members(self, root: Any, code: str) -> dict[str, set[str]]:
        """Extract value member names (properties/fields) for each class."""
        members: dict[str, set[str]] = {}
        for class_node in self._find_nodes(root, "class_declaration"):
            class_name = self._get_class_name(class_node, code)
            if not class_name:
                continue

            body = None
            for child in class_node.children:
                if child.type == "declaration_list":
                    body = child
                    break
            if body is None:
                members[class_name] = set()
                continue

            value_members = self._extract_value_members_from_class_body(body, code)
            members[class_name] = set(value_members.keys())
        return members

    def _extract_value_members_from_class_body(self, body: Any, code: str) -> dict[str, Any]:
        """Extract value members and source nodes from a class declaration body."""
        members: dict[str, Any] = {}
        for member in body.children:
            if member.type == "property_declaration":
                prop_name = self._get_property_name(member, code)
                if prop_name:
                    members[prop_name] = member
                continue
            if member.type != "field_declaration":
                continue
            for variable in self._find_nodes(member, "variable_declarator"):
                name_node = variable.child_by_field_name("name")
                if not name_node:
                    continue
                field_name = self._get_node_text(name_node, code)
                if field_name:
                    members[field_name] = member
        return members

    def _get_class_name(self, node: Any, code: str) -> str | None:
        """Get class name from class_declaration node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, code)
        return None

    def _get_enum_name(self, node: Any, code: str) -> str | None:
        """Get enum name from enum_declaration node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, code)
        return None

    def _get_property_name_from_source(self, attr_source: str) -> str | None:
        """Extract property name from a property declaration source fragment.

        Wraps the fragment in a minimal class and parses to get the property name.
        Returns None if parsing fails (caller will include the attr as a safeguard).
        """
        wrapped = f"namespace __ {{ class __ {{{attr_source}}} }}"
        try:
            tree = self.parse(wrapped)
            for prop in self._find_nodes(tree.root_node, "property_declaration"):
                name = self._get_property_name(prop, wrapped)
                if name:
                    return name
        except CodeMergeError:
            pass
        return None

    def _get_property_name(self, node: Any, code: str) -> str | None:
        """Get property name from property_declaration node.

        Uses child_by_field_name('name') per the tree-sitter grammar to reliably
        get the property name rather than the first identifier (which could be
        from the type, e.g. in explicit interface implementations).
        """
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._get_node_text(name_node, code)
        return None

    def _get_method_name(self, node: Any, code: str) -> str | None:
        """Get method name from method_declaration node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, code)
        return None

    def _extract_marked_sections(self, code: str) -> list[str]:
        """Extract code sections marked with // CUSTOM CODE comments."""
        sections = []
        lines = code.split("\n")
        in_section = False
        current_section: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped == self.CUSTOM_CODE_START:
                in_section = True
                current_section = []
            elif stripped == self.CUSTOM_CODE_END:
                if in_section and current_section:
                    sections.append("\n".join(current_section))
                in_section = False
                current_section = []
            elif in_section:
                current_section.append(line)

        return sections
