"""
Swift AST serializer.

Converts Swift AST nodes to formatted Swift source code:
- 4-space indentation
- ``import Foundation``
- structs conforming to ``Codable`` with a nested ``CodingKeys`` mapping to JSON keys
- a custom ``init(from:)`` (in an extension) when any property has a default, so the
  default is applied for a missing key (Swift's synthesized Codable ignores defaults)
- string/int raw-value enums
- discriminated polymorphic ``enum``s with ``init(from:)`` / ``encode(to:)``
"""

from __future__ import annotations

from .swift_ast_nodes import (
    SwiftEnum,
    SwiftFile,
    SwiftPolyEnum,
    SwiftStruct,
)


class SwiftSerializer:
    """Serializes Swift AST nodes to source code."""

    INDENT = "    "

    def serialize(self, file: SwiftFile) -> str:
        lines: list[str] = []

        if file.generation_comment:
            lines.append(file.generation_comment)
            lines.append("")

        for imp in file.imports:
            lines.append(f"import {imp}")
        if file.imports:
            lines.append("")

        blocks: list[list[str]] = []
        blocks.extend([self._serialize_enum(e)] for e in file.enums)
        blocks.extend([self._serialize_poly_enum(pe)] for pe in file.poly_enums)
        blocks.extend([self._serialize_struct(s)] for s in file.structs)

        # Flatten with a blank line between top-level declarations.
        flat: list[str] = []
        for i, block in enumerate(blocks):
            if i > 0:
                flat.append("")
            flat.extend(block[0])

        lines.extend(flat)
        return "\n".join(lines).rstrip() + "\n"

    # ------------------------------------------------------------------- enums

    def _serialize_enum(self, enum: SwiftEnum) -> list[str]:
        lines: list[str] = []
        if enum.comment:
            lines.append(f"// {enum.comment}")
        prefix = "nonisolated " if enum.nonisolated else ""
        conformances = ", ".join(enum.conformances)
        lines.append(f"{prefix}enum {enum.name}: {enum.raw_type}, {conformances} {{")
        for case in enum.cases:
            raw = f'"{case.raw_value}"' if enum.raw_type == "String" else case.raw_value
            lines.append(f"{self.INDENT}case {case.name} = {raw}")
        lines.append("}")
        return lines

    def _serialize_poly_enum(self, poly: SwiftPolyEnum) -> list[str]:
        lines: list[str] = []
        if poly.comment:
            lines.append(f"// {poly.comment}")
        prefix = "nonisolated " if poly.nonisolated else ""
        conformances = ", ".join(poly.conformances)
        lines.append(f"{prefix}enum {poly.name}: {conformances} {{")
        for case in poly.cases:
            lines.append(f"{self.INDENT}case {case.name}({case.concrete_type})")
        lines.append("")

        # Discriminator coding key
        lines.append(f"{self.INDENT}private enum DiscriminatorKeys: String, CodingKey {{")
        lines.append(f'{self.INDENT}{self.INDENT}case discriminator = "{poly.discriminator_key}"')
        lines.append(f"{self.INDENT}}}")
        lines.append("")

        # init(from:)
        lines.append(f"{self.INDENT}init(from decoder: Decoder) throws {{")
        lines.append(f"{self.INDENT}{self.INDENT}let container = try decoder.container(keyedBy: DiscriminatorKeys.self)")
        lines.append(f"{self.INDENT}{self.INDENT}let discriminator = try container.decode(String.self, forKey: .discriminator)")
        lines.append(f"{self.INDENT}{self.INDENT}switch discriminator {{")
        for case in poly.cases:
            lines.append(f'{self.INDENT}{self.INDENT}case "{case.discriminator_value}": ' f"self = .{case.name}(try {case.concrete_type}(from: decoder))")
        lines.append(f"{self.INDENT}{self.INDENT}default:")
        lines.append(
            f"{self.INDENT}{self.INDENT}{self.INDENT}throw DecodingError.dataCorruptedError("
            "forKey: .discriminator, in: container, "
            f'debugDescription: "Unknown discriminator \\(discriminator) for {poly.name}")'
        )
        lines.append(f"{self.INDENT}{self.INDENT}}}")
        lines.append(f"{self.INDENT}}}")
        lines.append("")

        # encode(to:) — only when the type actually encodes
        if not any(c in ("Codable", "Encodable") for c in poly.conformances):
            lines.append("}")
            return lines
        lines.append(f"{self.INDENT}func encode(to encoder: Encoder) throws {{")
        lines.append(f"{self.INDENT}{self.INDENT}switch self {{")
        for case in poly.cases:
            lines.append(f"{self.INDENT}{self.INDENT}case .{case.name}(let value): try value.encode(to: encoder)")
        lines.append(f"{self.INDENT}{self.INDENT}}}")
        lines.append(f"{self.INDENT}}}")
        lines.append("}")
        return lines

    # ----------------------------------------------------------------- structs

    def _serialize_struct(self, struct: SwiftStruct) -> list[str]:
        lines: list[str] = []
        if struct.comment:
            lines.append(f"// {struct.comment}")
        prefix = "nonisolated " if struct.nonisolated else ""
        conformances = ", ".join(struct.conformances)
        lines.append(f"{prefix}struct {struct.name}: {conformances} {{")

        for prop in struct.properties:
            keyword = "var" if prop.default_value is not None else "let"
            decl = f"{self.INDENT}{keyword} {prop.name}: {prop.type_name}"
            if prop.default_value is not None:
                decl += f" = {prop.default_value}"
            if prop.comment:
                decl += prop.comment
            lines.append(decl)

        # CodingKeys (always emitted: JSON keys are snake_case, properties lowerCamelCase)
        if struct.properties:
            lines.append("")
            lines.append(f"{self.INDENT}enum CodingKeys: String, CodingKey {{")
            for prop in struct.properties:
                lines.append(f'{self.INDENT}{self.INDENT}case {prop.name} = "{prop.json_key}"')
            lines.append(f"{self.INDENT}}}")

        lines.append("}")

        # Custom decoder in an extension (keeps the synthesized memberwise init available).
        if struct.needs_custom_decoder:
            lines.append("")
            # nonisolated must be restated: an extension is its own isolation scope,
            # so under default-MainActor projects the decoder witness would otherwise
            # be @MainActor while the conformance is nonisolated.
            lines.append(f"{prefix}extension {struct.name} {{")
            lines.append(f"{self.INDENT}init(from decoder: Decoder) throws {{")
            lines.append(f"{self.INDENT}{self.INDENT}let container = try decoder.container(keyedBy: CodingKeys.self)")
            for prop in struct.properties:
                lines.append(self._decode_statement(prop))
            lines.append(f"{self.INDENT}}}")
            lines.append("}")

        return lines

    def _decode_statement(self, prop) -> str:
        body = f"{self.INDENT}{self.INDENT}self.{prop.name} = "
        # Strip a trailing optional marker for the decoded type argument.
        base_type = prop.type_name[:-1] if prop.type_name.endswith("?") else prop.type_name
        if prop.default_value is not None:
            return body + f"try container.decodeIfPresent({base_type}.self, forKey: .{prop.name}) ?? {prop.default_value}"
        if prop.is_optional:
            return body + f"try container.decodeIfPresent({base_type}.self, forKey: .{prop.name})"
        return body + f"try container.decode({base_type}.self, forKey: .{prop.name})"
