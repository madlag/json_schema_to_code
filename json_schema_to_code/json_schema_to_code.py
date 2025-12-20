import json
from pathlib import Path

import click

from .pipeline import CodeGeneratorConfig, PipelineGenerator


@click.command()
@click.option("--name", "-n", default=None, type=str)
@click.option("--config", "-c", default=None, type=click.Path(exists=True, resolve_path=True))
@click.option("--language", "-l", default="cs", type=click.Choice(["cs", "python"]))
@click.option(
    "--add-validation",
    is_flag=True,
    default=False,
    help="Add runtime validation in __post_init__ (Python) or constructor (C#)",
)
@click.argument("path", default=None, type=click.Path(exists=True, resolve_path=True))
@click.argument("output", default=None, type=click.Path(resolve_path=True))
def json_schema_to_code(name, config, language, add_validation, path, output):
    with open(path) as f:
        schema = json.load(f)

    if config is not None:
        with open(config) as f:
            config = json.load(f)
            config = CodeGeneratorConfig.from_dict(config)
    else:
        config = CodeGeneratorConfig()

    # Apply CLI flag for validation (overrides config file if set)
    if add_validation:
        config.add_validation = True

    if name is None:
        name = Path(path).stem

    # Use AST-based pipeline generator
    codegen = PipelineGenerator(name, schema, config, language)

    out = codegen.generate()
    with open(output, "w") as f:
        f.write(out)
