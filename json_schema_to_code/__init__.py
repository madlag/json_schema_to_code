"""JSON Schema to Code Generator

A Python package for generating code from JSON Schema definitions.
Supports Python, C# and Swift code generation with AST-based pipeline,
code merging, and configurable output options.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version

# Read from the installed distribution rather than restated here: this was a
# hand-maintained copy and it drifted three releases behind (1.1.0 while
# pyproject said 1.1.4), so every generated file's header stamped the wrong
# generator version. pyproject.toml is now the single source.
try:
    __version__ = _metadata_version("json_schema_to_code")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+unknown"

__author__ = "François Lagunas"

from .pipeline import (
    AtomicWriter,
    CodeGeneratorConfig,
    CodeMergeError,
    FormatterConfig,
    MergeStrategy,
    OutputConfig,
    OutputMode,
    PipelineGenerator,
    PythonAstMerger,
)

__all__ = [
    "PipelineGenerator",
    "CodeGeneratorConfig",
    "FormatterConfig",
    "OutputConfig",
    "OutputMode",
    "MergeStrategy",
    "CodeMergeError",
    "PythonAstMerger",
    "AtomicWriter",
]
