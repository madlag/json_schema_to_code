"""x-swift-type: verbatim Swift type override on a property."""

from json_schema_to_code.pipeline.config import CodeGeneratorConfig
from json_schema_to_code.pipeline.generator import PipelineGenerator

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$defs": {
        "Card": {
            "type": "object",
            "properties": {
                "widgets": {
                    "type": "array",
                    "items": {"type": "object"},
                    "default": [],
                    "x-swift-type": "[NamedWidget]",
                },
                "template": {
                    "type": "object",
                    "x-swift-type": "JSONValue?",
                },
                "title": {"type": "string"},
            },
            "required": ["title", "template"],
        }
    },
    "$ref": "#/$defs/Card",
}


def _generate() -> str:
    return PipelineGenerator("Card", SCHEMA, CodeGeneratorConfig(), "swift").generate()


def test_x_swift_type_overrides_property_types():
    code = _generate()
    assert "var widgets: [NamedWidget] = []" in code
    assert "let template: JSONValue?" in code
    # untouched sibling keeps normal translation
    assert "let title: String" in code


def test_x_swift_type_decode_semantics():
    code = _generate()
    # container default survives -> decodeIfPresent ?? []
    assert "decodeIfPresent([NamedWidget].self, forKey: .widgets) ?? []" in code
    # optional override decodes leniently to nil
    assert "decodeIfPresent(JSONValue.self, forKey: .template)" in code


def test_swift_conformances_and_nonisolated():
    config = CodeGeneratorConfig()
    config.swift_conformances = ["Decodable", "Hashable", "Sendable"]
    config.swift_nonisolated = True
    code = PipelineGenerator("Card", SCHEMA, config, "swift").generate()
    assert "nonisolated struct Card: Decodable, Hashable, Sendable {" in code
    assert "Codable" not in code


def test_swift_nonisolated_covers_decoder_extension():
    config = CodeGeneratorConfig()
    config.swift_conformances = ["Decodable", "Hashable", "Sendable"]
    config.swift_nonisolated = True
    code = PipelineGenerator("Card", SCHEMA, config, "swift").generate()
    # the init(from:) extension is its own isolation scope: it must restate nonisolated
    assert "nonisolated extension Card {" in code
    assert "\nextension Card {" not in code
