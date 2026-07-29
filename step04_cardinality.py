"""Step 04: Detect attribute cardinalities (minOccurs/maxOccurs).

Multiplicities are rendered in UML notation after the attribute type:
[0..1], [0..*], [1..*], ... The UML default [1] (exactly one) is omitted
to keep the diagram readable.

Usage:
    python3 step04_cardinality.py [xsd_path] [output_path]
"""

import sys
from pathlib import Path

from step01_list_classes import default_output, diagram_title, parse_classes, qualify, schema_prefix, strip_type_suffix, target_namespace
from step02_inheritance import parse_inheritance
from step03_attributes import parse_attributes

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")


def multiplicity(attr: dict) -> str:
    """UML multiplicity string, empty for the default exactly-one."""
    lo = attr["min"]
    hi = "*" if attr["max"] == "unbounded" else attr["max"]
    if (lo, hi) == ("1", "1"):
        return ""
    if lo == hi:
        return f" [{lo}]"
    return f" [{lo}..{hi}]"


def to_plantuml(classes, relations, attributes, title, prefix, subtitle=None):
    known = {c["name"] for c in classes}

    def q(name: str) -> str:
        """Strip the "Type" suffix, then qualify local class names;
        external names are already prefixed."""
        stripped = strip_type_suffix(name)
        return qualify(stripped, prefix) if stripped in known else stripped

    lines = ["@startuml", "title", f"  {title}"]
    if subtitle:
        lines.append(f"  {subtitle}")
    lines += ["end title", ""]
    if prefix:
        lines.append(f"package {prefix} {{")
    for cls in classes:
        keyword = "abstract class" if cls["abstract"] else "class"
        line = f'{keyword} "{qualify(cls["name"], prefix)}"'
        if cls["name"].endswith("Property"):
            line += " $property"
        if cls["name"].startswith("ADEOf"):
            line += " $adeOf"
        attrs = attributes.get(cls["xsd_name"], [])
        if attrs:
            lines.append(line + " {")
            for attr in attrs:
                name = attr["name"]
                if name.startswith("adeOf"):
                    # ADE hook attributes are marked as package members (~ )
                    # and hidden via "hide package members" below.
                    name = f"~ {name}"
                elif attr["type"].partition(":")[0] != prefix:
                    # Value type from another namespace: marked as a protected
                    # member (# ) and hidden via "hide protected members" below.
                    name = f"# {name}"
                lines.append(f'  {name} : {attr["type"]}{multiplicity(attr)}')
            lines.append("}")
        else:
            lines.append(line)
    if prefix:
        lines.append("}")
    stubs = sorted({q(p) for _, p in relations} - {qualify(k, prefix) for k in known})
    if stubs:
        lines.append("")
        lines.append("' External base types (unresolved namespaces)")
        for stub in stubs:
            keyword = "abstract class" if stub.split(":")[-1].startswith("Abstract") else "class"
            lines.append(f'{keyword} "{stub}"')
    lines.append("")
    for child, parent in relations:
        lines.append(f'"{q(parent)}" <|-- "{q(child)}"')
    if any(c["name"].startswith("ADEOf") for c in classes):
        lines += ["", "' ADE hook classes are removed from rendering by default;",
                  "' remove the next line to show them.", "remove $adeOf"]
    if any(c["name"].endswith("Property") for c in classes):
        lines += ["", "' Property pseudo-classes are removed from rendering by default;",
                  "' remove the next line to show them.", "remove $property"]
    if any(a["name"].startswith("adeOf") for attrs in attributes.values() for a in attrs):
        lines += ["", "' ADE hook attributes are marked as package members (~ ) and",
                  "' hidden from rendering by default; remove the next line to show them.",
                  "hide package members"]
    if any(a["type"].partition(":")[0] != prefix for attrs in attributes.values() for a in attrs):
        lines += ["", "' Attributes with value types from other namespaces are marked as",
                  "' protected members (# ) and shown by default; uncomment the next",
                  "' line to hide them.", "' hide protected members"]
    lines += ["", "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    xsd_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XSD
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output(xsd_path)

    prefix = schema_prefix(xsd_path)
    classes = parse_classes(xsd_path)
    relations = parse_inheritance(xsd_path)
    attributes = parse_attributes(xsd_path, prefix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_plantuml(classes, relations, attributes, diagram_title(xsd_path),
                                    prefix, target_namespace(xsd_path)),
                        encoding="utf-8")
    total = sum(len(a) for a in attributes.values())
    print(f"{len(classes)} classes, {len(relations)} inheritance relations, "
          f"{total} attributes (with cardinalities) written to {out_path}")


if __name__ == "__main__":
    main()
