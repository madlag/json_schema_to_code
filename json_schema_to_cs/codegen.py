import json
from pathlib import Path
import jinja2
import copy
import collections


CURRENT_DIR = Path(__file__).parent.resolve().absolute()

class CodeGenerator:
    def __init__(self, name, schema, out_path):
        self.name = name
        self.schema = schema
        self.out_path = out_path

        self.jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)
        self.prefix = self.jinja_env.from_string(open(CURRENT_DIR/"templates/prefix.cs.jinja2").read())
        self.class_model = self.jinja_env.from_string(open(CURRENT_DIR/"templates/class.cs.jinja2").read())
        self.suffix = self.jinja_env.from_string(open(CURRENT_DIR/"templates/suffix.cs.jinja2").read())

        self.type_map = dict(integer="int", string="string", boolean="bool", number="float", null="null")

        self.subclasses = collections.defaultdict(list)
        self.base_class = dict()
        self.class_info = dict()

    def ref_type(self, ref):
        return ref.split("/")[-1]
    
    def translate_type(self, type_info):
        if "type" in type_info:
            type = type_info["type"]            
            if type == "array":
                item_type = self.translate_type(type_info["items"])
                type = f"List<{item_type}>"
            elif isinstance(type, list):
                nullable = False
                if "null" in type:
                    nullable = True
                    type.remove("null")

                if len(type) == 1:
                    type = self.translate_type({"type":type[0]})
                    if nullable:
                        type = type + "?"
                else:
                    type = "Or".join([self.translate_type({"type":t}).capitalize() for t in type]);
            
            else:
                return self.type_map[type]
        elif "$ref" in type_info:
            type = self.ref_type(type_info["$ref"])
        else:
            raise Exception("Unknown type " +  str(type_info))
        return type

    def convert_message_class_to_json_name(self, class_name):
        return class_name

    def preprocess(self, class_name, info):
        p = copy.deepcopy(info)
        if 'allOf' in p:
            base_class = self.ref_type(p['allOf'][0]['$ref'])
            # Change class_name camelcase to snake_case
            json_name = self.convert_message_class_to_json_name(class_name)
            self.subclasses[base_class].append([class_name, json_name])
            self.base_class[class_name] = base_class
        self.class_info[class_name] = p

    def prepare_class_info(self, class_name, info):
        p = copy.deepcopy(info)

        if 'allOf' in p:
            extends = self.ref_type(p['allOf'][0]['$ref'])
            p = p['allOf'][1]
            p["EXTENDS"] = extends

        p["CLASS_NAME"] = class_name
        p["SUB_CLASSES"] = self.subclasses.get(class_name, [])

        properties = p["properties"]

        if p.get("EXTENDS") is not None:
            p["BASE_PROPERTIES"] = dict()

            bc = self.base_class[class_name]
            if (bc not in self.class_info):
                raise Exception(f"Base class {bc} not found for class {class_name}")
            p_base = self.class_info.get(bc)
            new_properties = dict()
            for property, property_info in p_base["properties"].items():
                if property != "type":
                    property_info["TYPE"] = self.translate_type(property_info)
                    new_properties[property] = property_info
                    p["BASE_PROPERTIES"][property] = property_info
                else:
                    p["BASE_PROPERTIES"]["nameof(" + class_name + ")"] = property_info
            for property, property_info in properties.items():
                property_info["TYPE"] = self.translate_type(property_info)
                new_properties[property] = property_info
            p["constructor_properties"] = new_properties
        else:
            p["constructor_properties"] = properties
            
        for property, property_info in properties.items():
            property_info["TYPE"] = self.translate_type(property_info)
        

        return p
    
    def generate(self):
        definitions = self.schema.get("definitions", {})
        for k,v in definitions.items():
            self.preprocess(k, v)

        self.prepare_class_info(self.name, self.schema)

        out = self.prefix.render()
        for k,v in definitions.items():
            p = self.prepare_class_info(k, v)
            s = self.class_model.render(p)
            out += s + "\n"

        out += self.suffix.render()

        with open(self.out_path, "w") as f:
            f.write(out)

    def generate_model(self, model):
        with open(f"{self.out_dir}/{model.name}.py", "w") as f:
            f.write(f"class {model.name}:\n")
            for field in model.fields:
                f.write(f"    {field.name}: {field.type}\n")






