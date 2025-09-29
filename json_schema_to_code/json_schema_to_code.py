import json
from pathlib import Path

import click

from .codegen import CodeGenerator, CodeGeneratorConfig


@click.command()
@click.option("--name", "-n", default=None, type=str)
@click.option("--config", "-c", default=None, type=click.Path(exists=True, resolve_path=True))
@click.option("--language", "-l", default="cs", type=click.Choice(["cs", "python"]))
@click.argument("path", default=None, type=click.Path(exists=True, resolve_path=True))
@click.argument("output", default=None, type=click.Path(resolve_path=True))
def json_schema_to_code(name, config, language, path, output):
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

    codegen = CodeGenerator(name, schema, config, language)
    out = codegen.generate()
    with open(output, "w") as f:
        f.write(out)


if __name__ == "__main__":
    import sys

    base = Path("/Users/lagunas/devel/")
    project_base = Path("/Users/lagunas/devel/public/json_schema_to_code")
    #    input = base / "ai/dh-server/dhserver/models/schemas/messages_schema.json"
    input = (
        base
        / "edu/explayn_main/python/explayn-dh-agent/explayn_dh_agent/barbara/ui/ui_hierarchy_schema.json"
    )
    language_to_extension = {"cs": "cs", "python": "py"}

    outputs = {
        "python": base / "ai/dh-server/client/python/",
        "cs": base / "ai/dh-server/client/cs/",
    }
    outputs = {
        "python": base
        / "edu/explayn_main/python/explayn-dh-agent/explayn_dh_agent/barbara/ui/ui_hierarchy.py",
        "cs": base
        / "edu/explayn_main/python/explayn-dh-agent/explayn_dh_agent/barbara/ui/ui_hierarchy.cs",
    }

    generate = {"python": ["agent"]}  # "cs": ["client"],
    #    generate = {"cs": ["client"]}
    for language, code_types in generate.items():
        for code_type in code_types:
            output = str(outputs[language])
            # config = base / outputs[language] / f"{code_type}_messages_generate_config.json"

            config_file = (
                base
                / "edu/explayn_main/python/explayn-dh-agent/explayn_dh_agent/barbara/ui/ui_hierarchy_config.json"
            )
            sys.argv = [
                "json_schema_to_code",
                str(input),
                str(output),
                "-c",
                str(config_file),
                "-l",
                language,
            ]
            # sys.argv = ["json_schema_to_code", str(input), str(output), "-l", language]

            json_schema_to_code()
