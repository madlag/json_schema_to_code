"""`x-omit-when-default`: a field is left out of the JSON while it holds its default.

Serialization behaviour only shows at runtime, so the generated module is executed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$ref": "#/$defs/Root",
    "$defs": {
        "Root": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "count": {"type": "integer", "default": 0, "x-omit-when-default": True},
                "label": {"type": "string", "x-omit-when-default": True},
                "tags": {"type": "array", "items": {"type": "string"}, "default": [], "x-omit-when-default": True},
                "inner": {"$ref": "#/$defs/Inner", "x-omit-when-default": True},
                "kept": {"type": "integer", "default": 0},
            },
            "required": ["kind"],
        },
        "Inner": {
            "type": "object",
            "properties": {"name": {"type": "string", "default": ""}, "n": {"type": "integer", "default": 0}},
        },
    },
}


def generate(schema: dict, **config_overrides: Any) -> str:
    config = CodeGeneratorConfig(add_generation_comment=False, **config_overrides)
    return PipelineGenerator("Root", schema, config, "python").generate()


def load(code: str, tmp_path: Path, name: str) -> Any:
    path = tmp_path / f"{name}.py"
    path.write_text(code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_fields_at_their_default_are_omitted_from_the_json(tmp_path: Path):
    module = load(generate(SCHEMA), tmp_path, "omit_a")

    # Only the flagged fields disappear; `kept` stays at its default in the output.
    assert module.Root(kind="x").to_dict() == {"kind": "x", "kept": 0}
    assert module.Root.from_dict({"kind": "x"}).to_dict() == {"kind": "x", "kept": 0}


def test_fields_away_from_their_default_are_serialized(tmp_path: Path):
    module = load(generate(SCHEMA), tmp_path, "omit_b")
    root = module.Root(kind="x", count=2, label="l", tags=["t"], inner=module.Inner(n=1))

    assert root.to_dict() == {"kind": "x", "count": 2, "label": "l", "tags": ["t"], "inner": {"name": "", "n": 1}, "kept": 0}
    assert module.Root.from_dict(root.to_dict()) == root


def test_an_all_default_sub_object_is_omitted(tmp_path: Path):
    """A class-typed field is compared against a freshly built default instance."""
    module = load(generate(SCHEMA), tmp_path, "omit_c")

    assert "inner" not in module.Root(kind="x", inner=module.Inner()).to_dict()
    assert "inner" in module.Root(kind="x", inner=module.Inner(name="set")).to_dict()


def test_omit_goes_through_the_configured_helper():
    """With optional_field_helper_module the scalar defaults use the project's helper,
    exactly as exclude_default_value_from_json does; the class-typed one stays inline."""
    code = generate(SCHEMA, optional_field_helper_module="app.helpers")

    assert "from app.helpers import optional_field_in_json" in code
    assert "count: int = optional_field_in_json(default=0)" in code
    assert "inner: Inner = field(default_factory=lambda: Inner(), metadata=config(exclude=lambda x: x == Inner().to_dict()))" in code
    assert "kept: int = 0" in code


def test_omit_on_a_required_field_without_a_default_is_a_schema_error():
    schema = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$ref": "#/$defs/Root",
        "$defs": {
            "Root": {
                "type": "object",
                "properties": {"kind": {"type": "string", "x-omit-when-default": True}},
                "required": ["kind"],
            }
        },
    }
    with pytest.raises(ValueError, match="x-omit-when-default on 'kind'"):
        generate(schema)
