import json
import unittest
from pathlib import Path
from unittest import TestCase

from json_schema_to_code.codegen import CodeGenerator, CodeGeneratorConfig


def json_schema_to_code(name, path):
    with open(path) as f:
        schema = json.load(f)

    if name is None:
        name = Path(path).stem

    config = CodeGeneratorConfig()
    config.use_inline_unions = False  # Disable union processing for C# tests for now
    codegen = CodeGenerator(name, schema, config, "cs")  # Original tests use C#
    out = codegen.generate()
    return out


class TestFun(TestCase):
    def test_dh_client(self):
        p = Path(__file__).parent / "test_data" / "schemas"
        p_in = p / "dhclient.schema.json"
        p_ref = p / "dhclient.cs"
        s = json_schema_to_code("dh_client", p_in)

        out = Path(__file__).parent / "schemas_out"
        out.mkdir(exist_ok=True)
        with open(out / "dhclient.cs", "w") as f:
            f.write(s)

        with open(p_ref) as f:
            ref = f.read()
        self.assertEqual(s, ref)

    def test_geometry(self):
        p = Path(__file__).parent / "test_data" / "schemas"
        p_in = p / "geometry.schema.json"
        p_ref = p / "geometry.cs"
        s = json_schema_to_code("geometry", p_in)

        out = Path(__file__).parent / "schemas_out"
        out.mkdir(exist_ok=True)
        with open(out / "geometry.cs", "w") as f:
            f.write(s)

        with open(p_ref) as f:
            ref = f.read()

        self.assertEqual(s, ref)


if __name__ == "__main__":
    unittest.main()
