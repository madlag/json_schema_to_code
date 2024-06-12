import json
from pathlib import Path

import click
from codegen import CodeGenerator


@click.command()
@click.option("--name", "-n", default=None, type=str)
@click.argument("path", default=None, type=click.Path(exists=True, resolve_path=True))
@click.argument("output", default=None, type=click.Path(resolve_path=True))
def json_schema_to_code(name, path, output):
    with open(path) as f:
        schema = json.load(f)

    if name is None:
        name = Path(path).stem

    codegen = CodeGenerator(name, schema)
    out = codegen.generate()
    with open(output, "w") as f:
        f.write(out)


if __name__ == "__main__":
    json_schema_to_code()
