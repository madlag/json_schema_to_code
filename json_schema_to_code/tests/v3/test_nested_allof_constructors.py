"""
Regression tests for the C# code generator on multi-level ``allOf``
inheritance chains (grandchild -> parent -> grandparent).

Bug fixed: when ``GrandchildClass`` extends ``ParentClass`` (via ``allOf``)
which itself extends ``GrandparentClass`` (also via ``allOf``), the
constructor's ``: base(...)`` call must match the **immediate parent's**
constructor signature, not the full flattened ancestor properties.
Specifically, fields the parent constifies at its own level (typical
discriminator pattern) are absorbed by the parent's constructor and must
**not** be passed by the grandchild's ``base(...)`` call.

Before the fix, the analyzer flattened ancestor properties + parent
extension properties, producing duplicate same-name entries (e.g. the
``type`` discriminator) and yielding a ``base(...)`` call with too many
arguments (and a duplicated literal) that did not match the parent's
constructor.
"""

from __future__ import annotations

import re

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator

# Three-level allOf chain that mirrors the WidgetImage / ImageByURL /
# ImageBySearch hierarchy. ``Grandparent`` declares a non-const discriminator
# ``type``; ``Parent`` constifies it and adds two own fields; ``Grandchild``
# re-constifies it and adds one own field.
NESTED_ALLOF_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$defs": {
        "Grandparent": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "type": {"type": "string"},
                "thumbnail": {"type": "string"},
            },
            "required": ["object_id", "type"],
        },
        "Parent": {
            "allOf": [
                {"$ref": "#/$defs/Grandparent"},
                {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "Parent"},
                        "image_url": {"type": "string"},
                        "resize": {"type": "boolean"},
                    },
                    "required": ["type", "image_url"],
                },
            ]
        },
        "Grandchild": {
            "allOf": [
                {"$ref": "#/$defs/Parent"},
                {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "Grandchild"},
                        "search_query": {"type": "string"},
                    },
                    "required": ["type", "search_query"],
                },
            ]
        },
    },
    "$ref": "#/$defs/Grandchild",
}


def _generate_csharp(schema: dict, class_name: str = "Root") -> str:
    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    return PipelineGenerator(class_name, schema, config, "cs").generate()


def _extract_constructor(code: str, class_name: str) -> str:
    """Return the constructor signature line for ``class_name``.

    Looks for ``public ClassName(...)``: matches the parameter list and any
    ``: base(...)`` chaining call, but stops before the body. Raises if not
    found.
    """
    pattern = rf"public {class_name}\([^{{]*?\)(?:\s*:\s*base\([^{{]*?\))?"
    match = re.search(pattern, code)
    if match is None:
        raise AssertionError(f"Constructor for {class_name} not found in:\n{code}")
    return match.group(0)


def _count_base_args(constructor_sig: str) -> int:
    """Count comma-separated args in the ``: base(...)`` call. Returns 0 if no base call."""
    base_match = re.search(r":\s*base\((.*)\)", constructor_sig, re.DOTALL)
    if not base_match:
        return 0
    args = base_match.group(1).strip()
    if not args:
        return 0
    # Naive comma split — fine for our schemas (no nested calls inside args).
    return len([a for a in args.split(",") if a.strip()])


def test_parent_base_call_skips_no_parent_const():
    """Single-level allOf: Parent's base() passes the const literal for the
    grandparent's non-const ``type`` field. base(object_id, "Parent",
    thumbnail) → 3 args (object_id + literal + thumbnail)."""
    code = _generate_csharp(NESTED_ALLOF_SCHEMA)
    sig = _extract_constructor(code, "Parent")
    assert _count_base_args(sig) == 3, f"Parent base() args wrong: {sig}"
    assert '"Parent"' in sig, f"Parent base() should pass type literal: {sig}"


def test_grandchild_base_call_matches_parent_constructor():
    """Two-level allOf: Grandchild's base() must call Parent's constructor,
    which takes (object_id, thumbnail, image_url, resize) — 4 args. The
    ``type`` field is constified at Parent's level, so Parent's constructor
    does NOT take it; Grandchild's base() must NOT pass any literal for it.
    """
    code = _generate_csharp(NESTED_ALLOF_SCHEMA)
    sig = _extract_constructor(code, "Grandchild")
    n = _count_base_args(sig)
    assert n == 4, f"Grandchild base() should have 4 args (object_id, thumbnail, " f"image_url, resize) but has {n}: {sig}"
    # Grandchild's own const ``type`` is expressed via the override property,
    # not the constructor — the literal must NOT appear in base().
    base_call = re.search(r":\s*base\((.*?)\)", sig).group(1)
    assert '"Grandchild"' not in base_call, f"Grandchild base() should not pass type literal " f"(parent constructor doesn't take it): {sig}"
    assert '"Parent"' not in base_call, f"Grandchild base() should not pass parent's type literal: {sig}"


def test_grandchild_property_override():
    """The Grandchild's own ``type`` const is emitted as an override getter
    on its own class, not via the constructor."""
    code = _generate_csharp(NESTED_ALLOF_SCHEMA)
    assert re.search(r'public override string Type => "Grandchild";', code), f"Grandchild should emit override getter for Type:\n{code}"


def test_parent_property_override():
    code = _generate_csharp(NESTED_ALLOF_SCHEMA)
    assert re.search(r'public override string Type => "Parent";', code), f"Parent should emit override getter for Type:\n{code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
