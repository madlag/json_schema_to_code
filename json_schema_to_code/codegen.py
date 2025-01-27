import collections
import copy
from pathlib import Path

import jinja2

CURRENT_DIR = Path(__file__).parent.resolve().absolute()

class CodeGeneratorConfig:
    ignoreSubClassOverrides: bool = False
    drop_min_max_items: bool = False
    use_array_of_super_type_for_variable_length_tuple:bool = True
    use_tuples:bool = True

    @staticmethod
    def from_dict(d):
        config = CodeGeneratorConfig()
        for k, v in d.items():
            setattr(config, k, v)
        return config

class CodeGenerator:
    def __init__(self, class_name: str, schema: str, config: CodeGeneratorConfig):
        self.class_name = class_name
        self.schema = schema
        self.config = config

        self.jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)
        self.prefix = self.jinja_env.from_string(
            open(CURRENT_DIR / "templates/prefix.cs.jinja2").read()
        )
        self.class_model = self.jinja_env.from_string(
            open(CURRENT_DIR / "templates/class.cs.jinja2").read()
        )
        self.suffix = self.jinja_env.from_string(
            open(CURRENT_DIR / "templates/suffix.cs.jinja2").read()
        )

        self.type_map = dict(
            integer="int", string="string", boolean="bool", number="float", null="null"
        )

        self.subclasses = collections.defaultdict(list)
        self.base_class = dict()
        self.class_info = dict()

    def ref_type(self, ref):
        return ref.split("/")[-1]
    
    def super_type(self, items):
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
                    type = f"List<{item_type}>"
                elif isinstance(type_info["items"], list):
                    if type_info.get("minItems") != type_info.get("maxItems"):
                        if not self.config.drop_min_max_items:
                            raise Exception("Variable length tuple is not supported")

                    if type_info.get("minItems") != type_info.get("maxItems") or not self.config.use_tuples:
                        if not self.config.use_array_of_super_type_for_variable_length_tuple:
                            # Check if all items are of the same type
                            item_types = [
                                self.translate_type(t)["type"]
                                for t in type_info["items"]
                            ]

                            for item_type in item_types[1:]:
                                # Items are not of the same type
                                if item_type != item_types[0]:
                                    raise Exception("The items are not of the same type: " + str(item_types))
                        item_type = self.super_type(type_info["items"])
                        item_type = self.translate_type(item_type)
                        type = f"List<{item_type['type']}>"
                    elif self.config.use_tuples:
                        item_types = [
                            self.translate_type(t)["type"]
                            for t in type_info["items"]
                        ]
                        type = f"Tuple<{', '.join(item_types)}>"

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
                        type = type + "?"
                else:
                    typeNames = [
                            self.translate_type({"type": t})["type"].capitalize()
                            for t in type
                        ]
                    typeNames.sort()
                    type = "Or".join(typeNames)
            else:
                return {"type": self.type_map[type]}
        elif "$ref" in type_info:
            type = self.ref_type(type_info["$ref"])
        elif "const" in type_info:
            type = type_info["const"]
            return {"init": type}
        elif "enum" in type_info:
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
            self.subclasses[base_class].append([class_name, json_name])
            self.base_class[class_name] = base_class
        self.class_info[class_name] = p

    def prepare_class_info(self, class_name, info):
        p = copy.deepcopy(info)

        if "allOf" in p:
            extends = self.ref_type(p["allOf"][0]["$ref"])
            p = p["allOf"][1]
            p["EXTENDS"] = extends

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

        return p

    def generate(self):
        definitions = self.schema.get("definitions", {})
        for k, v in definitions.items():
            self.preprocess(k, v)

        self.prepare_class_info(self.class_name, self.schema)

        out = self.prefix.render()
        for k, v in definitions.items():
            p = self.prepare_class_info(k, v)
            s = self.class_model.render(p)
            out += s + "\n"

        out += self.suffix.render()

        return out
