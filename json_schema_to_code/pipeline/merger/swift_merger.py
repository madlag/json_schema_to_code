"""
Swift AST merger implementation.

Uses tree-sitter and tree-sitter-swift to preserve hand-written code when a Swift
file is regenerated. Idiomatic Swift keeps custom code in separate ``extension``
blocks, so the merger preserves:

- custom ``import`` statements not emitted by the generator,
- custom members (``func`` / computed ``var``) added inside a generated type,
- whole custom top-level declarations (user ``extension`` blocks, helper types and
  free functions) that the generator does not produce,
- ``// CUSTOM CODE START/END`` marked raw sections.

Stored properties are considered generated data (driven by the schema) and are not
preserved as "custom" -- add or remove them in the schema, not by hand.
"""

from __future__ import annotations

from typing import Any

from .base import AstMerger, CodeMergeError, CustomCode

try:
    import tree_sitter_swift as ts_swift
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None


class SwiftAstMerger(AstMerger):
    """Merger for Swift source files using tree-sitter."""

    STANDARD_IMPORTS = {"Foundation"}

    CUSTOM_CODE_START = "// CUSTOM CODE START"
    CUSTOM_CODE_END = "// CUSTOM CODE END"

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise CodeMergeError("tree-sitter and tree-sitter-swift are required for Swift merging. " "Install with: pip install tree-sitter tree-sitter-swift")
        self._parser = Parser(Language(ts_swift.language()))

    # ----------------------------------------------------------------- AstMerger

    def parse(self, code: str) -> Any:
        tree = self._parser.parse(bytes(code, "utf8"))
        if tree.root_node.has_error:
            errors = self._find_nodes(tree.root_node, "ERROR")
            if errors:
                first = errors[0]
                snippet = self._text(first, code)[:50]
                raise CodeMergeError(f"Failed to parse Swift code at line {first.start_point[0] + 1}: " f"syntax error near {snippet!r}")
        return tree

    def extract_custom_code(self, existing_code: str, generated_code: str) -> CustomCode:
        existing_tree = self.parse(existing_code)
        generated_tree = self.parse(generated_code)

        custom = CustomCode()

        generated_imports = self._extract_imports(generated_tree.root_node, generated_code)
        generated_types = self._extract_type_names(generated_tree.root_node, generated_code)
        generated_members = self._extract_type_members(generated_tree.root_node, generated_code)
        generated_ext_members = self._extract_extension_members(generated_tree.root_node, generated_code)

        root = existing_tree.root_node

        # Custom imports
        for node in self._top_level(root, "import_declaration"):
            text = self._text(node, existing_code).strip()
            module = self._import_module(text)
            if module and module not in generated_imports and module not in self.STANDARD_IMPORTS:
                custom.custom_imports.append(text)

        # Top-level declarations (struct/class/enum/extension), direct children only.
        for node in self._top_level(root, "class_declaration"):
            if self._is_extension(node):
                self._handle_existing_extension(node, existing_code, generated_ext_members, custom)
            else:
                self._handle_existing_type(node, existing_code, generated_types, generated_members, custom)

        # Top-level free functions
        for node in self._top_level(root, "function_declaration"):
            custom.custom_classes.append(self._text(node, existing_code))

        custom.raw_sections = self._extract_marked_sections(existing_code)
        return custom

    def merge(self, generated_code: str, custom_code: CustomCode) -> str:
        lines = generated_code.split("\n")
        result: list[str] = []

        # Insert custom imports right after the last generated import line.
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("import "):
                last_import_idx = i

        tree = self.parse(generated_code)
        # Map generated type name -> last line index of its body (to append members).
        type_close_line: dict[str, int] = {}
        for node in self._top_level(tree.root_node, "class_declaration"):
            if self._is_extension(node):
                continue
            name = self._type_name(node, generated_code)
            if name:
                type_close_line[name] = node.end_point[0]

        for i, line in enumerate(lines):
            # Append custom members just before a generated type's closing brace.
            for name, close_line in type_close_line.items():
                if i == close_line and name in custom_code.class_methods:
                    for member in custom_code.class_methods[name]:
                        result.append("")
                        for mline in member.split("\n"):
                            result.append("    " + mline if mline.strip() else mline)
            result.append(line)
            if i == last_import_idx and custom_code.custom_imports:
                for imp in custom_code.custom_imports:
                    result.append(imp)

        # Append custom top-level declarations and raw sections at end of file.
        tail: list[str] = []
        for decl in custom_code.custom_classes:
            tail.append("")
            tail.append(decl)
        for section in custom_code.raw_sections:
            tail.append("")
            tail.append(section)

        merged = "\n".join(result).rstrip() + "\n"
        if tail:
            merged = merged + "\n".join(tail).rstrip() + "\n"
        return merged

    def validate(self, code: str) -> None:
        self.parse(code)
        if "struct " not in code and "enum " not in code and "class " not in code:
            raise CodeMergeError("Merged Swift code has no type definitions")

    # --------------------------------------------------------------- extraction

    def _handle_existing_extension(self, node, code, generated_ext_members, custom) -> None:
        type_name = self._extension_target(node, code)
        members = self._member_names(node, code)
        gen_members = generated_ext_members.get(type_name, set())
        # Skip the generator-owned extension (its members are all generated, e.g. init(from:)).
        if members and members.issubset(gen_members):
            return
        if not members:
            return
        custom.custom_classes.append(self._text(node, code))

    def _handle_existing_type(self, node, code, generated_types, generated_members, custom) -> None:
        name = self._type_name(node, code)
        if not name:
            return
        if name not in generated_types:
            # A hand-written helper type the generator doesn't produce.
            custom.custom_classes.append(self._text(node, code))
            return
        # Generated type: preserve custom behavior members (func / computed property).
        gen_members = generated_members.get(name, set())
        for member, member_name in self._behavior_members(node, code):
            if member_name not in gen_members:
                custom.class_methods.setdefault(name, []).append(self._text(member, code))

    def _extract_imports(self, root, code) -> set[str]:
        modules = set()
        for node in self._top_level(root, "import_declaration"):
            module = self._import_module(self._text(node, code).strip())
            if module:
                modules.add(module)
        return modules

    def _extract_type_names(self, root, code) -> set[str]:
        names = set()
        for node in self._top_level(root, "class_declaration"):
            if self._is_extension(node):
                continue
            name = self._type_name(node, code)
            if name:
                names.add(name)
        return names

    def _extract_type_members(self, root, code) -> dict[str, set[str]]:
        members: dict[str, set[str]] = {}
        for node in self._top_level(root, "class_declaration"):
            if self._is_extension(node):
                continue
            name = self._type_name(node, code)
            if name:
                members[name] = self._member_names(node, code)
        return members

    def _extract_extension_members(self, root, code) -> dict[str, set[str]]:
        members: dict[str, set[str]] = {}
        for node in self._top_level(root, "class_declaration"):
            if not self._is_extension(node):
                continue
            target = self._extension_target(node, code)
            if target:
                members.setdefault(target, set()).update(self._member_names(node, code))
        return members

    def _extract_marked_sections(self, code: str) -> list[str]:
        sections: list[str] = []
        current: list[str] = []
        in_section = False
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped == self.CUSTOM_CODE_START:
                in_section = True
                current = []
            elif stripped == self.CUSTOM_CODE_END:
                if in_section and current:
                    sections.append("\n".join(current))
                in_section = False
                current = []
            elif in_section:
                current.append(line)
        return sections

    # -------------------------------------------------------------- tree helpers

    def _top_level(self, root, node_type: str) -> list[Any]:
        return [c for c in root.children if c.type == node_type]

    def _find_nodes(self, node, node_type: str) -> list[Any]:
        out = []
        if node.type == node_type:
            out.append(node)
        for child in node.children:
            out.extend(self._find_nodes(child, node_type))
        return out

    def _text(self, node, code: str) -> str:
        return code[node.start_byte : node.end_byte]

    def _is_extension(self, node) -> bool:
        # struct/class/enum start with a `type_identifier` name child; an extension's
        # first named child is the extended `user_type`.
        for child in node.named_children:
            if child.type == "type_identifier":
                return False
            if child.type == "user_type":
                return True
        return False

    def _type_name(self, node, code: str) -> str | None:
        for child in node.named_children:
            if child.type == "type_identifier":
                return self._text(child, code)
        return None

    def _extension_target(self, node, code: str) -> str | None:
        for child in node.named_children:
            if child.type == "user_type":
                return self._text(child, code)
        return None

    def _body(self, node) -> Any | None:
        for child in node.children:
            if child.type in ("class_body", "enum_class_body"):
                return child
        return None

    def _member_names(self, node, code: str) -> set[str]:
        names: set[str] = set()
        body = self._body(node)
        if not body:
            return names
        for member in body.children:
            if member.type == "function_declaration":
                fname = self._function_name(member, code)
                if fname:
                    names.add(fname)
            elif member.type == "property_declaration":
                pname = self._property_name(member, code)
                if pname:
                    names.add(pname)
            elif member.type in ("init_declaration", "deinit_declaration"):
                names.add(member.type)
        return names

    def _behavior_members(self, node, code: str) -> list[tuple[Any, str]]:
        """Functions and computed properties (custom behavior), not stored properties."""
        out: list[tuple[Any, str]] = []
        body = self._body(node)
        if not body:
            return out
        for member in body.children:
            if member.type == "function_declaration":
                fname = self._function_name(member, code)
                if fname:
                    out.append((member, fname))
            elif member.type == "property_declaration" and self._find_nodes(member, "computed_property"):
                pname = self._property_name(member, code)
                if pname:
                    out.append((member, pname))
        return out

    def _function_name(self, node, code: str) -> str | None:
        for child in node.named_children:
            if child.type == "simple_identifier":
                return self._text(child, code)
        return None

    def _property_name(self, node, code: str) -> str | None:
        for child in node.named_children:
            if child.type == "pattern":
                ident = self._find_nodes(child, "simple_identifier")
                if ident:
                    return self._text(ident[0], code)
        return None

    def _import_module(self, import_text: str) -> str | None:
        text = import_text.strip()
        if text.startswith("import "):
            return text[len("import ") :].strip()
        return None
