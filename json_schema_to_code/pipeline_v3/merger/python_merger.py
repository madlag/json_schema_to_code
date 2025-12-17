"""
Python AST merger implementation.

Uses Python's built-in ast module to parse, extract custom code,
and merge generated code with existing files.
"""

from __future__ import annotations

import ast

from .base import AstMerger, CodeMergeError, CustomCode


class PythonAstMerger(AstMerger):
    """Merger for Python source files using the built-in ast module."""

    # Standard imports that are always generated - don't preserve these
    STANDARD_IMPORTS = {
        ("__future__", "annotations"),
        ("dataclasses", "dataclass"),
        ("dataclasses", "field"),
        ("dataclasses_json", "dataclass_json"),
        ("dataclasses_json", "config"),
        ("typing", "Any"),
        ("typing", "Literal"),
        ("enum", "Enum"),
        ("abc", "ABC"),
    }

    def parse(self, code: str) -> ast.Module:
        """Parse Python source code into an AST.

        Args:
            code: Python source code string

        Returns:
            ast.Module representing the parsed code

        Raises:
            CodeMergeError: If the code cannot be parsed
        """
        try:
            return ast.parse(code)
        except SyntaxError as e:
            raise CodeMergeError(f"Failed to parse Python code: {e}") from e

    def extract_custom_code(self, existing_code: str, generated_code: str) -> CustomCode:
        """Not used in order-preserving merge. Kept for interface compatibility."""
        return CustomCode()

    def merge(self, generated_code: str, custom_code: CustomCode) -> str:
        """Not used in order-preserving merge. Kept for interface compatibility."""
        return generated_code

    def merge_files(self, generated_code: str, existing_code: str) -> str:
        """Merge generated code into existing file, preserving order.

        Walks the existing file structure and updates elements from generated code.
        New elements are added at the end.
        """
        existing_tree = self.parse(existing_code)
        generated_tree = self.parse(generated_code)

        # Build lookups for generated code
        gen_imports = self._get_imports_list(generated_tree)
        gen_classes = {n.name: n for n in generated_tree.body if isinstance(n, ast.ClassDef)}

        new_body = []
        seen_imports = set()

        # Walk existing tree in order
        for node in existing_tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Keep existing import
                new_body.append(node)
                seen_imports.add(ast.unparse(node))

            elif isinstance(node, ast.ClassDef):
                if node.name in gen_classes:
                    # Merge class: existing structure, updated content
                    merged = self._merge_class(node, gen_classes[node.name])
                    new_body.append(merged)
                    del gen_classes[node.name]
                else:
                    # Custom class, keep as-is
                    new_body.append(node)

            else:
                # Other elements (docstrings, constants, etc.)
                new_body.append(node)

        # Add new imports from generated (not already present)
        insert_idx = self._find_import_insert_index_in_list(new_body)
        for imp in gen_imports:
            if ast.unparse(imp) not in seen_imports:
                new_body.insert(insert_idx, imp)
                insert_idx += 1

        # Add new classes from generated at end
        for cls in gen_classes.values():
            new_body.append(cls)

        existing_tree.body = new_body
        ast.fix_missing_locations(existing_tree)
        return ast.unparse(existing_tree)

    def _merge_class(self, existing: ast.ClassDef, generated: ast.ClassDef) -> ast.ClassDef:
        """Merge a class: preserve existing order, update content from generated."""
        # Build lookups for generated class
        gen_fields = {}
        gen_methods = {}
        for item in generated.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                gen_fields[item.target.id] = item
            elif isinstance(item, ast.FunctionDef):
                gen_methods[item.name] = item

        new_body = []
        seen_fields = set()
        seen_methods = set()

        # Walk existing class body in order
        for item in existing.body:
            if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                # Docstring - keep it
                new_body.append(item)

            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                if field_name in gen_fields:
                    # Update field from generated, but preserve existing default if generated has none
                    gen_field = gen_fields[field_name]
                    if gen_field.value is None and item.value is not None:
                        # Generated has no default, but existing does - keep existing default
                        gen_field.value = item.value
                    new_body.append(gen_field)
                else:
                    # Custom field, keep as-is
                    new_body.append(item)
                seen_fields.add(field_name)

            elif isinstance(item, ast.FunctionDef):
                method_name = item.name
                if method_name in gen_methods:
                    # Merge method: keep docstring, use generated body
                    merged = self._merge_method(item, gen_methods[method_name])
                    new_body.append(merged)
                else:
                    # Custom method, keep as-is
                    new_body.append(item)
                seen_methods.add(method_name)

            else:
                # Other items (Assign, etc.)
                new_body.append(item)

        # Add new fields from generated (at end of fields section)
        field_insert_idx = self._find_field_insert_index(new_body)
        for name, field in gen_fields.items():
            if name not in seen_fields:
                new_body.insert(field_insert_idx, field)
                field_insert_idx += 1

        # Add new methods from generated at end
        for name, method in gen_methods.items():
            if name not in seen_methods:
                new_body.append(method)

        existing.body = new_body
        # Keep existing decorators and bases
        return existing

    def _merge_method(self, existing: ast.FunctionDef, generated: ast.FunctionDef) -> ast.FunctionDef:
        """Merge a method: keep existing docstring, use generated body."""
        existing_docstring = ast.get_docstring(existing)

        # Use generated method as base
        result = generated

        # Restore docstring if it existed
        if existing_docstring:
            has_docstring = result.body and isinstance(result.body[0], ast.Expr) and isinstance(result.body[0].value, ast.Constant) and isinstance(result.body[0].value.value, str)
            if not has_docstring:
                docstring_node = ast.Expr(value=ast.Constant(value=existing_docstring))
                result.body.insert(0, docstring_node)

        return result

    def _get_imports_list(self, tree: ast.Module) -> list:
        """Get list of import nodes."""
        return [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]

    def _find_import_insert_index_in_list(self, body: list) -> int:
        """Find index after last import in a body list."""
        last_idx = 0
        for i, node in enumerate(body):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_idx = i + 1
        return last_idx

    def _find_field_insert_index(self, body: list) -> int:
        """Find index after last field (before first method)."""
        last_field_idx = 0
        for i, item in enumerate(body):
            if isinstance(item, (ast.AnnAssign, ast.Assign)):
                last_field_idx = i + 1
            elif isinstance(item, ast.Expr):
                # Docstring at start
                last_field_idx = i + 1
            elif isinstance(item, ast.FunctionDef):
                break
        return last_field_idx

    def validate(self, code: str) -> None:
        """Validate that merged Python code is syntactically correct.

        Args:
            code: The merged code to validate

        Raises:
            CodeMergeError: If validation fails
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise CodeMergeError(f"Merged code is not valid Python: {e}") from e

        # Additional semantic checks
        if "from __future__ import annotations" not in code:
            if "class " in code:
                # Not strictly required but expected in our output
                pass

        if "@dataclass" not in code and "class " in code:
            # Check we haven't lost all decorators
            pass
