"""Defaults for fields that may be absent, and what the merger does when they change.

Two failures that only show up at runtime, so both are exercised by executing the
generated module rather than by matching strings.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator
from json_schema_to_code.pipeline.config import MergeStrategy
from json_schema_to_code.pipeline.merger import PythonAstMerger

ENUM_REF_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$ref": "#/$defs/Root",
    "$defs": {
        "Root": {
            "type": "object",
            "properties": {"kind": {"type": "string"}, "state": {"$ref": "#/$defs/State"}},
            "required": ["kind"],
        },
        "State": {"type": "string", "enum": ["A", "B"]},
    },
}


def load(code: str, tmp_path: Path) -> Any:
    path = tmp_path / "generated.py"
    path.write_text(code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("generated_optional", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_optional"] = module
    spec.loader.exec_module(module)
    return module


def generate(schema: dict) -> str:
    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    return PipelineGenerator("Root", schema, config, "python").generate()


def test_absent_enum_field_is_optional(tmp_path: Path):
    """`E()` raises TypeError, so an enum can never take an empty-instance default."""
    code = generate(ENUM_REF_SCHEMA)

    assert "state: State | None = None" in code
    assert "State()" not in code


def test_generated_module_survives_the_absent_enum(tmp_path: Path):
    """The regression: the dataclass could be neither constructed nor deserialized."""
    module = load(generate(ENUM_REF_SCHEMA), tmp_path)

    assert module.Root(kind="x").state is None
    assert module.Root.from_dict({"kind": "x"}).state is None
    assert module.Root.from_dict({"kind": "x", "state": "A"}).state == module.State.A


def merge(generated: str, existing: str) -> str:
    return PythonAstMerger().merge_files(generated, existing, MergeStrategy.MERGE)


HEADER = "from dataclasses import dataclass\n\n\n@dataclass\nclass P:\n"


def field_lines(code: str) -> list[str]:
    return [line.strip() for line in code.splitlines() if ":" in line and "class" not in line]


def test_merge_drops_a_default_the_new_annotation_invalidates():
    """A field that stopped being optional must not keep its `= None`.

    Splicing the old default onto the new annotation yields `X = None`, which is in
    neither input and annotates a required field as if it could be None.
    """
    merged = merge(HEADER + "    sim: Simulation\n", HEADER + "    sim: Simulation | None = None\n")

    assert field_lines(merged) == ["sim: Simulation"]


def test_merge_still_keeps_a_default_when_the_type_is_unchanged():
    """The behaviour the rule exists for: hand-set defaults survive regeneration."""
    merged = merge(HEADER + "    label: str\n", HEADER + "    label: str = 'hand-set'\n")

    assert field_lines(merged) == ["label: str = 'hand-set'"]


def test_merge_keeps_a_default_when_the_field_becomes_optional():
    """Widening is still a change of annotation -- the generated declaration wins."""
    merged = merge(HEADER + "    sim: Simulation | None = None\n", HEADER + "    sim: Simulation\n")

    assert field_lines(merged) == ["sim: Simulation | None = None"]
