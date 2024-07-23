import json
from pathlib import Path

import click
from .codegen import CodeGenerator, CodeGeneratorConfig


@click.command()
@click.option("--name", "-n", default=None, type=str)
@click.option("--config", "-c", default=None, type=click.Path(exists=True, resolve_path=True))
@click.argument("path", default=None, type=click.Path(exists=True, resolve_path=True))
@click.argument("output", default=None, type=click.Path(resolve_path=True))
def json_schema_to_code(name, config, path, output):
    with open(path) as f:
        schema = json.load(f)
    if config is not None:
        with open(config) as f:
            config = json.load(f)
            config = CodeGeneratorConfig.from_dict(config)
    else:
        config = CodeGeneratorConfig()

    if name is None:
        name = Path(path).stem

    codegen = CodeGenerator(name, schema, config)
    out = codegen.generate()
    with open(output, "w") as f:
        f.write(out)


if __name__ == "__main__":
    json_schema_to_code()
