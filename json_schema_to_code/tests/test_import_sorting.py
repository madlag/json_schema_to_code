"""Formatter: isort grouping of the generated imports.

The Python backend emits imports in a fixed order (`__future__`, then modules
alphabetically) and leaves the grouping -- stdlib, third party, first party, with a
blank line between -- to ruff, because the grouping depends on which modules are
first-party to the project consuming the generated file, knowledge that lives in
that project's ruff config, not here.

Without the isort pass, any project whose own lint sorts imports rewrites every
generated file on the next commit, which reads as generator drift when it is not.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from json_schema_to_code.pipeline import CodeGeneratorConfig, PipelineGenerator

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$ref": "#/$defs/Root",
    "$defs": {
        "Root": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "items": {"type": "array", "items": {"type": "string"}},
                "state": {"$ref": "#/$defs/State"},
            },
            "required": ["kind"],
        },
        "State": {"type": "string", "enum": ["A", "B"]},
    },
}


def generate(tmp_path: Path, *, sort_imports: bool) -> list[str]:
    config = CodeGeneratorConfig()
    config.add_generation_comment = False
    config.formatter.sort_imports = sort_imports
    out = tmp_path / "generated.py"
    PipelineGenerator("Root", SCHEMA, config, "python").generate_to_file(out)
    return out.read_text(encoding="utf-8").splitlines()


def import_block(lines: list[str]) -> list[str]:
    """Lines up to (and including) the last import, blank lines preserved."""
    last = max(i for i, line in enumerate(lines) if line.startswith(("import ", "from ")))
    return lines[: last + 1]


def groups(block: list[str]) -> list[list[str]]:
    """Split an import block into its blank-line-separated groups."""
    out: list[list[str]] = [[]]
    for line in block:
        if line:
            out[-1].append(line)
        elif out[-1]:
            out.append([])
    return [g for g in out if g]


def test_import_groups_are_blank_line_separated(tmp_path: Path):
    block = import_block(generate(tmp_path, sort_imports=True))
    found = groups(block)

    # __future__, then stdlib, then third party -- asserted by group membership rather
    # than exact names, which shift as the backend's own imports change.
    assert len(found) == 3, found
    assert found[0] == ["from __future__ import annotations"]
    assert all(line.startswith(("from dataclasses import", "from enum import")) for line in found[1]), found[1]
    assert found[2] == ["from dataclasses_json import dataclass_json"]


def test_sorting_is_idempotent(tmp_path: Path):
    """A second generation must not churn the file -- the point of the option."""
    first = generate(tmp_path, sort_imports=True)
    second = generate(tmp_path, sort_imports=True)

    assert first == second


def test_opting_out_leaves_the_backend_order(tmp_path: Path):
    block = import_block(generate(tmp_path, sort_imports=False))

    assert "" not in block
    # `__future__` first, then alphabetical by module: deterministic, ungrouped
    assert block[0] == "from __future__ import annotations"
    modules = [line.split()[1] for line in block[1:]]
    assert modules == sorted(modules), modules


def test_sorting_is_on_by_default():
    assert CodeGeneratorConfig().formatter.sort_imports is True
