"""`x-python-default` / `x-python-default-code`: a constructor default that leaves `required` alone.

The wire contract (validation demands the property) and the constructor's convenience
(the class fills the field in) are different questions; a schema answers both.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator


def load(code: str, tmp_path: Path, name: str = "generated_language_defaults") -> Any:
    path = tmp_path / f"{name}.py"
    path.write_text(code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def generate(schema: dict, language: str = "python") -> str:
    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    return PipelineGenerator("Root", schema, config, language).generate()


def root_with(extra_props: dict, defs: dict | None = None) -> dict:
    """Root{kind (required), **extra_props (all required)}."""
    return {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$ref": "#/$defs/Root",
        "$defs": {
            "Root": {
                "type": "object",
                "properties": {"kind": {"type": "string"}, **extra_props},
                "required": ["kind", *extra_props],
            },
            **(defs or {}),
        },
    }


INNER = {"Inner": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}


@pytest.fixture
def mylib():
    module = types.ModuleType("mylib")
    module.make_id = lambda: "made-id"
    sys.modules["mylib"] = module
    yield module
    del sys.modules["mylib"]


def test_code_default_fills_a_required_field(tmp_path: Path, mylib):
    """The property stays required (the schema still says so); the constructor fills it."""
    schema = root_with({"id": {"type": "string", "x-python-default-code": "field(default_factory=make_id)", "x-python-imports": ["from mylib import make_id"]}})
    code = generate(schema)

    assert "id: str = field(default_factory=make_id)" in code
    assert "from mylib import make_id" in code
    assert "from dataclasses import dataclass, field" in code

    module = load(code, tmp_path)
    assert module.Root(kind="x").id == "made-id"
    assert module.Root.from_dict({"kind": "x"}).id == "made-id"
    assert module.Root.from_dict({"kind": "x", "id": "given"}).id == "given"


def test_plain_import_statement(tmp_path: Path):
    schema = root_with({"id": {"type": "string", "x-python-default-code": "field(default_factory=lambda: uuid.uuid4().hex[:8])", "x-python-imports": ["import uuid"]}})
    code = generate(schema)

    assert "import uuid" in code
    module = load(code, tmp_path, "generated_plain_import")
    assert len(module.Root(kind="x").id) == 8


def test_value_default_on_a_required_class_field_builds_the_instance(tmp_path: Path):
    schema = root_with({"inner": {"$ref": "#/$defs/Inner", "x-python-default": {"name": "n"}}}, INNER)
    code = generate(schema)

    assert "inner: Inner = field(default_factory=lambda: Inner.from_dict({'name': 'n'}))" in code

    module = load(code, tmp_path, "generated_value_default")
    assert module.Root(kind="x").inner.name == "n"
    assert module.Root(kind="x").to_dict() == {"kind": "x", "inner": {"name": "n"}}


def test_null_value_default_widens_the_annotation(tmp_path: Path):
    schema = root_with({"inner": {"$ref": "#/$defs/Inner", "x-python-default": None}}, INNER)
    code = generate(schema)

    assert "inner: Inner | None = None" in code
    module = load(code, tmp_path, "generated_null_default")
    assert module.Root(kind="x").inner is None


def test_scalar_value_default(tmp_path: Path):
    code = generate(root_with({"month": {"type": "integer", "x-python-default": 0}, "label": {"type": "string", "x-python-default": ""}}))

    assert "month: int = 0" in code
    assert 'label: str = ""' in code or "label: str = ''" in code
    module = load(code, tmp_path, "generated_scalar_default")
    assert module.Root(kind="x").month == 0


def test_value_default_on_an_optional_scalar_keeps_the_annotation_plain(tmp_path: Path):
    """An optional scalar is normally widened to `T | None` to express absence; a
    constructor default expresses it instead, so the annotation stays `T`."""
    schema = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$ref": "#/$defs/Root",
        "$defs": {
            "Root": {
                "type": "object",
                "properties": {"kind": {"type": "string"}, "keyword": {"type": "string", "x-python-default": ""}, "note": {"type": "string"}},
                "required": ["kind"],
            }
        },
    }
    code = generate(schema)

    assert 'keyword: str = ""' in code or "keyword: str = ''" in code
    assert "keyword: str | None" not in code
    assert "note: str | None = None" in code  # untouched: no default of any kind

    module = load(code, tmp_path, "generated_optional_scalar")
    assert module.Root(kind="x").keyword == ""


def test_a_defaulted_required_field_is_ordered_after_the_bare_ones():
    """A field with a constructor default cannot precede one without (dataclass rule)."""
    code = generate(root_with({"month": {"type": "integer", "x-python-default": 0}, "day": {"type": "integer"}}))
    body = code.split("class Root")[1]
    assert body.index("day: int") < body.index("month: int = 0")


def test_other_backends_keep_the_field_required():
    schema = root_with({"inner": {"$ref": "#/$defs/Inner", "x-python-default": {"name": "n"}}}, INNER)
    swift = generate(schema, "swift")

    assert '"n"' not in swift
    assert "Inner?" not in swift


def test_default_and_code_together_is_an_error():
    schema = root_with({"month": {"type": "integer", "x-python-default": 0, "x-python-default-code": "0"}})
    with pytest.raises(ValueError, match="both given"):
        generate(schema)


def test_a_bad_import_is_an_error():
    schema = root_with({"id": {"type": "string", "x-python-default-code": "make_id()", "x-python-imports": ["make_id = 1"]}})
    with pytest.raises(ValueError, match="not a single import statement"):
        generate(schema)
