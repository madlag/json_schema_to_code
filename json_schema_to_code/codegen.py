import collections
import copy
from pathlib import Path
import traceback
from typing import Any, Dict

import jinja2

CURRENT_DIR = Path(__file__).parent.resolve().absolute()


class CodeGeneratorConfig:
    ignore_classes: list[str] = []
    global_ignore_fields: list[str] = []
    order_classes: list[str] = []
    ignoreSubClassOverrides: bool = False
    drop_min_max_items: bool = False
    use_array_of_super_type_for_variable_length_tuple: bool = True
    use_tuples: bool = True

    @staticmethod
    def from_dict(d):
        config = CodeGeneratorConfig()
        for k, v in d.items():
            setattr(config, k, v)
        return config


class CodeGenerator:
    def __init__(self, class_name: str, schema: str, config: CodeGeneratorConfig, language: str):
        self.class_name = class_name
        self.schema = schema
        self.config = config
        self.language = language
        self.jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)
        language_to_extension = {
            "cs": "cs",
            "python": "py"
        }
        extension = language_to_extension[language]
        self.prefix = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/prefix.{extension}.jinja2").read()
        )
        self.class_model = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/class.{extension}.jinja2").read()
        )
        self.suffix = self.jinja_env.from_string(
            open(CURRENT_DIR / f"templates/{language}/suffix.{extension}.jinja2").read()
        )
                
        self.language_type_maps = {
            "cs": dict(
                integer="int", string="string", boolean="bool", number="float", null="null"
            ),
            "python": dict(
                integer="int", string="str", boolean="bool", number="float", null="None", object="Any"
            )
        }
        if language not in self.language_type_maps:
            raise Exception("Language not supported: " + language)
        self.type_map = self.language_type_maps[language]

        self.language_type_brackets = {
            "cs": "<>",
            "python": "[]"
        }
        if language not in self.language_type_brackets:
            raise Exception("Language not supported: " + language)
        self.type_brackets = self.language_type_brackets[language]        

        self.subclasses = collections.defaultdict(list)
        self.base_class = dict()
        self.class_info = dict()

    def optional_type(self, type: str) -> str:
        match self.language:
            case "python":
                t = type + " | None"
                return {"type": t, "init": "None"}
            case "cs":
                t = type + "?"
                return {"type": t}
            case _:
                raise Exception("Fix optional type for " + self.language)
        
    def union_type(self, types: list[str]) -> str:
        match self.language:
            case "python":
                return " | ".join(types)
            case "cs":
                raise Exception("Fix Union type for cs")
            case _:
                raise Exception("Fix Union type for " + self.language)
            
    def const_type(self, t: Dict[str, Any]) -> Dict[str, Any]:
        match self.language:
            case "python":
                const = t["const"]
                return {"type": f"Literal[\"{const}\"]", "init": f"\"{const}\""}
            case "cs":
                return {"type": t["type"], "init": t["const"], "modifier": "const"}
            case _:
                raise Exception("Fix const type for " + self.language)
            
    def ref_type(self, ref: str) -> str:
        return ref.split("/")[-1]

    def super_type(self, items: Dict[str, Any]):
        types = set()
        for item in items:
            if "type" in item:
                if isinstance(item["type"], list):
                    for t in item["type"]:
                        types.add(t)
                elif isinstance(item["type"], str):
                    types.add(item["type"])
            else:
                raise Exception("Unknown type " + str(item))
        types = list(types)
        types.sort()
        return {"type": types}

    def translate_type(self, type_info):
        if "type" in type_info:
            type = type_info["type"]
            if type == "array":
                if isinstance(type_info["items"], dict):
                    item_type_info = self.translate_type(type_info["items"])
                    item_type = item_type_info["type"]
                    type = f"List{self.type_brackets[0]}{item_type}{self.type_brackets[1]}"
                elif isinstance(type_info["items"], list):
                    if type_info.get("minItems") != type_info.get("maxItems"):
                        if not self.config.drop_min_max_items:
                            raise Exception("Variable length tuple is not supported")

                    if (
                        type_info.get("minItems") != type_info.get("maxItems")
                        or not self.config.use_tuples
                    ):
                        if not self.config.use_array_of_super_type_for_variable_length_tuple:
                            # Check if all items are of the same type
                            item_types = [
                                self.translate_type(t)["type"]
                                for t in type_info["items"]
                            ]

                            for item_type in item_types[1:]:
                                # Items are not of the same type
                                if item_type != item_types[0]:
                                    raise Exception(
                                        "The items are not of the same type: "
                                        + str(item_types)
                                    )
                        item_type = self.super_type(type_info["items"])
                        item_type = self.translate_type(item_type)
                        type = f"List{self.type_brackets[0]}{item_type['type']}{self.type_brackets[1]}"
                    elif self.config.use_tuples:
                        item_types = [
                            self.translate_type(t)["type"] for t in type_info["items"]
                        ]
                        type = f"Tuple{self.type_brackets[0]}{', '.join(item_types)}{self.type_brackets[1]}"

                else:
                    raise Exception("Unknown type " + str(type_info["items"]))
            elif isinstance(type, list):
                nullable = False
                if "null" in type:
                    nullable = True
                    type.remove("null")

                if len(type) == 1:
                    type = self.translate_type({"type": type[0]})["type"]
                    if nullable:
                        return self.optional_type(type)
                else:
                    typeNames = [
                        self.translate_type({"type": t})["type"].capitalize()
                        for t in type
                    ]
                    typeNames.sort()
                    type = "Or".join(typeNames)
            else:
                t = self.type_map[type]

                if "const" in type_info:
                    return self.const_type(type_info)
                return {"type": t}
        elif "$ref" in type_info:
            type = self.ref_type(type_info["$ref"])
        elif "const" in type_info:
            type = type_info["const"]
            return {"init": type}
        elif "enum" in type_info:
            # TODO deduplicate code handling enums here and lower 
            class_name = None
            for e in type_info["enum"]:
                c = e.__class__.__name__
                if class_name is None or c == class_name:
                    class_name = c
                else:
                    raise Exception("Enums with different types are not supported")
            mapping = {"str": "string", "int": "integer", "float": "float"}
            class_name = mapping.get(class_name, class_name)
            Warning(
                f"We should have information about what values are allowed for enum {class_name}"
            )
            comment = "// Allowed values: " + ", ".join(
                [f'"{e}"' for e in type_info["enum"]]
            )
            return {"type": self.type_map[class_name], "comment": comment}
        elif "oneOf" in type_info:
            types = [self.translate_type(t)["type"] for t in type_info["oneOf"]]
            return {"type": self.union_type(types)}
        else:
            raise Exception("Unknown type " + str(type_info))
        return {"type": type}

    def convert_message_class_to_json_name(self, properties, class_name):
        if "type" in properties:
            if "const" in properties["type"]:
                return properties["type"]["const"]
        return class_name

    def preprocess(self, class_name, info):
        p = copy.deepcopy(info)
        if "allOf" in p:
            allOf = p["allOf"]
            base_class = self.ref_type(allOf[0]["$ref"])
            # Change class_name camelcase to snake_case
            json_name = self.convert_message_class_to_json_name(
                allOf[1].get("properties", {}), class_name
            )
            if class_name not in self.config.ignore_classes:
                self.subclasses[base_class].append([class_name, json_name])
            self.base_class[class_name] = base_class
        self.class_info[class_name] = p

    def prepare_class_info(self, class_name, info):
        p = copy.deepcopy(info)

        if "allOf" in p:
            extends = self.ref_type(p["allOf"][0]["$ref"])
            p = p["allOf"][1]
            p["EXTENDS"] = extends
        if p["type"] != "object":
            base_type = self.translate_type(p)["type"]
            p["EXTENDS"] = base_type
            self.base_class[class_name] = base_type
            if base_type not in self.class_info:
                self.class_info[base_type] = {"properties":{}}

        p["CLASS_NAME"] = class_name
        p["SUB_CLASSES"] = self.subclasses.get(class_name, [])

        properties = p.get("properties", {})

        if p.get("EXTENDS") is not None:
            p["BASE_PROPERTIES"] = dict()

            bc = self.base_class[class_name]
            if bc not in self.class_info:
                raise Exception(f"Base class {bc} not found for class {class_name}")
            p_base = self.class_info.get(bc)
            constructor_properties = dict()
            for property, property_info in p_base["properties"].items():
                if property != "type":
                    TYPE = self.translate_type(property_info)
                    if "TYPE" not in property_info:
                        property_info["TYPE"] = {}
                    property_info["TYPE"].update(TYPE)
                    constructor_properties[property] = property_info
                    p["BASE_PROPERTIES"][property] = property_info
                else:
                    init_value = (
                        '"'
                        + self.convert_message_class_to_json_name(
                            properties, class_name
                        )
                        + '"'
                    )
                    #                    init_value = "nameof(" + class_name + ")"
                    p["BASE_PROPERTIES"][init_value] = property_info
            new_properties = dict()
            for property, property_info in properties.items():
                override_base_property = property in p["BASE_PROPERTIES"]
                if override_base_property and self.config.ignoreSubClassOverrides:
                    continue

                TYPE = self.translate_type(property_info)
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"].update(TYPE)
                type_modifier = "new " if override_base_property else ""
                property_info["TYPE"]["modifier"] = type_modifier

                if "type" in TYPE:
                    constructor_properties[property] = property_info
                    new_properties[property] = property_info

                p["properties"] = new_properties
                p["constructor_properties"] = constructor_properties
        else:            
            p["constructor_properties"] = properties

            for property, property_info in properties.items():
                TYPE = self.translate_type(property_info)
                if "TYPE" not in property_info:
                    property_info["TYPE"] = {}
                property_info["TYPE"].update(TYPE)

        if "enum" in p:
            p["enum"] = {k.upper(): k for k in p["enum"]}
        else:
            p["enum"] = {}


        if "properties" in p:
            p["properties"] = {k: v for k, v in p["properties"].items() if k not in self.config.global_ignore_fields}
        else:
            p["properties"] = {}
        if "constructor_properties" in p:
            p["constructor_properties"] = {k: v for k, v in p["constructor_properties"].items() if k not in self.config.global_ignore_fields}

        return p

    def generate(self):
        definitions = self.schema.get("definitions") or self.schema.get("$defs")
        if definitions is None:
            raise Exception("No definitions found in schema")

        for k, v in definitions.items():
            self.preprocess(k, v)

        if "properties" in self.schema:
            self.prepare_class_info(self.class_name, self.schema)

        out = self.prefix.render()

        def run_class_generator(k, v):
            nonlocal out
            if k in self.config.ignore_classes:
                return
            p = self.prepare_class_info(k, v)
            try:
                s = self.class_model.render(p)
                out += s + "\n"
            except Exception as e:
                print(f"Error generating class {k}: {e}")
                raise e from None

        for k in self.config.order_classes:
            run_class_generator(k, definitions[k])

        for k, v in definitions.items():
            if k not in self.config.order_classes:
                run_class_generator(k, v)

        out += self.suffix.render()

        return out
