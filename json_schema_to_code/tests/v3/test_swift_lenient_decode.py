"""Swift lenient decoding: schema defaults survive base-class flattening, and
non-required fields without defaults decode as optionals (never strict decode).

Miniature of the mimir-ios EstimateUIData case: an external allOf base whose
fields all carry schema defaults, plus a non-required bare-$ref field.
"""

import json

from json_schema_to_code.pipeline.config import CodeGeneratorConfig
from json_schema_to_code.pipeline.generator import PipelineGenerator

ACTIVITY_SCHEMA = {
    "$defs": {
        "UIData": {
            "type": "object",
            "properties": {
                "widgets": {
                    "type": "array",
                    "items": {"type": "object"},
                    "default": [],
                    "x-swift-type": "[NamedWidget]",
                }
            },
        },
        "ActivityUIData": {
            "allOf": [
                {"$ref": "#/$defs/UIData"},
                {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "default": ""},
                        "is_complete": {"type": "boolean", "default": False},
                    },
                },
            ]
        },
        "UIActionTemplate": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
        },
    }
}

ESTIMATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$defs": {
        "EstimateUIData": {
            "allOf": [
                {"$ref": "/activities/activity_schema#/$defs/ActivityUIData"},
                {
                    "type": "object",
                    "properties": {
                        "min": {"type": "number", "default": 0},
                        "actionTemplate": {"$ref": "/activities/activity_schema#/$defs/UIActionTemplate"},
                    },
                    "required": ["min"],
                },
            ]
        }
    },
    "$ref": "#/$defs/EstimateUIData",
}

LOCAL_BASE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$defs": {
        "Base": {
            "type": "object",
            "properties": {"kind": {"type": "string", "default": "none"}},
        },
        "Child": {
            "allOf": [
                {"$ref": "#/$defs/Base"},
                {"type": "object", "properties": {"value": {"type": "number", "default": 0}}},
            ]
        },
    },
    "$ref": "#/$defs/Child",
}


def _generate_estimate(tmp_path) -> str:
    activities = tmp_path / "activities"
    activities.mkdir()
    (activities / "activity_schema.json").write_text(json.dumps(ACTIVITY_SCHEMA))
    config = CodeGeneratorConfig()
    config.schema_base_path = str(tmp_path)
    return PipelineGenerator("EstimateUIData", ESTIMATE_SCHEMA, config, "swift").generate()


def test_external_base_defaults_survive_flattening(tmp_path):
    code = _generate_estimate(tmp_path)
    assert "var widgets: [NamedWidget] = []" in code
    assert "decodeIfPresent([NamedWidget].self, forKey: .widgets) ?? []" in code
    assert 'var question: String = ""' in code
    assert 'decodeIfPresent(String.self, forKey: .question) ?? ""' in code
    assert "var isComplete: Bool = false" in code


def test_required_field_with_default_stays_lenient(tmp_path):
    code = _generate_estimate(tmp_path)
    assert "var min: Double = 0" in code
    assert "decodeIfPresent(Double.self, forKey: .min) ?? 0" in code


def test_non_required_field_without_default_is_optional(tmp_path):
    code = _generate_estimate(tmp_path)
    assert "let actionTemplate: UIActionTemplate?" in code
    assert "decodeIfPresent(UIActionTemplate.self, forKey: .actionTemplate)" in code


def test_no_strict_decode_remains(tmp_path):
    # Every field is defaulted or optional: nothing may hard-fail the payload.
    code = _generate_estimate(tmp_path)
    assert " = try container.decode(" not in code


def test_local_base_defaults_survive_flattening():
    code = PipelineGenerator("Child", LOCAL_BASE_SCHEMA, CodeGeneratorConfig(), "swift").generate()
    assert 'var kind: String = "none"' in code
    assert 'decodeIfPresent(String.self, forKey: .kind) ?? "none"' in code
