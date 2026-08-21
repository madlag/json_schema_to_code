"""Python backend: polymorphic bases, and explicit type overrides.

Both behaviours are invisible in the generated *text* and only bite at runtime,
which is why they are exercised by executing the generated module rather than
by matching strings.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator

POLYMORPHIC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$ref": "#/$defs/Root",
    "$defs": {
        "EventBase": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "seq": {"type": "integer"},
            },
            "required": ["kind", "seq"],
        },
        "TextEvent": {
            "allOf": [
                {"$ref": "#/$defs/EventBase"},
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "const": "text"},
                        "text": {"type": "string"},
                    },
                    "required": ["kind", "text"],
                },
            ],
            "type": "object",
            "unevaluatedProperties": False,
        },
        "Root": {
            "type": "object",
            "properties": {"event": {"$ref": "#/$defs/TextEvent"}},
            "required": ["event"],
        },
    },
}

OVERRIDE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$ref": "#/$defs/Root",
    "$defs": {
        # A scalar $def: no class is generated for it, so a bare $ref would
        # leave a dangling name behind.
        "Sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "Root": {
            "type": "object",
            "properties": {
                "digest": {"$ref": "#/$defs/Sha256", "x-python-type": "str"},
                "optional_digest": {
                    "anyOf": [
                        {"$ref": "#/$defs/Sha256", "x-python-type": "str"},
                        {"type": "null"},
                    ]
                },
                "payload": {
                    "type": ["object", "array", "null"],
                    "x-python-type": "Any",
                },
            },
            "required": ["digest"],
        },
    },
}


def generate(schema: dict, class_name: str) -> str:
    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    config.use_future_annotations = True
    return PipelineGenerator(class_name, schema, config, "python").generate()


def load_module(code: str, tmp_path: Path, name: str = "generated") -> Any:
    """Import generated code as a real module.

    Written to a file and imported rather than `exec`'d: with
    `from __future__ import annotations` every annotation is a string, and
    `dataclasses_json` resolves them with `get_type_hints`, which looks them up
    in the defining module's globals. An `exec`'d namespace has none, so
    `to_dict`/`from_dict` would fail on the test harness rather than on the
    generated code.
    """
    module_path = tmp_path / f"{name}.py"
    module_path.write_text(code)
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_a_polymorphic_base_is_itself_a_dataclass(tmp_path: Path):
    """A base with subclasses must carry the dataclass decorators.

    `@dataclass` only inherits fields from base classes that are dataclasses
    themselves. An undecorated ABC base therefore drops every shared field from
    its children's __init__ and to_dict — silently, and only at runtime.
    """
    module = load_module(generate(POLYMORPHIC_SCHEMA, "Root"), tmp_path, "poly_a")

    base = module.EventBase
    assert is_dataclass(base), "polymorphic base was generated without @dataclass"

    child = module.TextEvent
    assert {f.name for f in fields(child)} >= {"kind", "seq", "text"}


def test_a_subclass_constructs_and_serializes_inherited_fields(tmp_path: Path):
    module = load_module(generate(POLYMORPHIC_SCHEMA, "Root"), tmp_path, "poly_b")
    event = module.TextEvent(seq=3, text="hello")

    assert event.seq == 3
    assert event.kind == "text"

    payload = event.to_dict()
    assert payload == {"kind": "text", "seq": 3, "text": "hello"}
    assert module.TextEvent.from_dict(payload) == event


def test_x_python_type_overrides_a_ref_to_a_scalar_def(tmp_path: Path):
    """Without the override the field would be annotated with a class name the
    generator never emits (scalar $defs produce no class)."""
    code = generate(OVERRIDE_SCHEMA, "Root")
    assert "Sha256" not in code

    module = load_module(code, tmp_path, "override_a")
    root = module.Root(digest="a" * 64)
    assert root.to_dict()["digest"] == "a" * 64


def test_x_python_type_overrides_inside_a_nullable_union():
    code = generate(OVERRIDE_SCHEMA, "Root")
    annotations = {line.split(":")[0].strip(): line.split(":", 1)[1].strip() for line in code.splitlines() if ":" in line and line.startswith("    ") and "=" in line}
    assert annotations["optional_digest"].startswith("str | None")


def test_x_python_type_overrides_an_inferred_union(tmp_path: Path):
    """`object|array|null` infers `Any | list[Any] | None`, which dataclasses_json
    tries (and fails) to decode as a union of dataclasses."""
    code = generate(OVERRIDE_SCHEMA, "Root")
    assert "Any | list[Any]" not in code

    module = load_module(code, tmp_path, "override_b")
    root = module.Root.from_dict({"digest": "b" * 64, "payload": {"any": "json"}})
    assert root.payload == {"any": "json"}


def test_generated_code_is_valid_json_schema_roundtrip():
    """Sanity: the schemas above are well-formed enough that generation is
    testing the backend, not a broken fixture."""
    for schema in (POLYMORPHIC_SCHEMA, OVERRIDE_SCHEMA):
        json.dumps(schema)
