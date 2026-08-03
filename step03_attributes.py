"""Step 03: Populate classes with attributes and their value types.

Every <element> declared inside a top-level complexType (including those
added via complexContent/extension) becomes a UML attribute. The value type
is shown with its namespace prefix, also for external schemas (gml:, xAL:).
Unprefixed built-in XML Schema types (e.g. anyURI) are shown as "xs:<name>".

Usage:
    python3 step03_attributes.py [xsd_path] [output_path]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from step01_list_classes import XSD_NS, default_output, diagram_title, generation_footer, parse_classes, qualify, schema_prefix, strip_property_suffix, strip_type_suffix, target_namespace
from step02_inheritance import parse_inheritance

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")

XMLSCHEMA_URI = "http://www.w3.org/2001/XMLSchema"


def default_namespace(xsd_path: Path) -> str:
    """The URI bound to the default (unprefixed) namespace."""
    for event, (prefix, uri) in ET.iterparse(xsd_path, events=["start-ns"]):
        if prefix == "":
            return uri
    return ""


def format_type(type_name: str, local_prefix: str | None, default_uri: str) -> str:
    """Format a type reference with its namespace prefix for display.

    The XSD encoding suffixes "Type" and "Property" are removed, so an
    attribute's value type reads as the target class name (e.g.
    core:ADEOfAddress instead of core:ADEOfAddressPropertyType).
    """
    prefix, sep, _ = type_name.partition(":")
    if sep:  # already prefixed (local or external schema)
        return strip_property_suffix(strip_type_suffix(type_name))
    if default_uri == XMLSCHEMA_URI:  # unprefixed XSD built-in, e.g. anyURI
        return f"xs:{type_name}"
    return qualify(strip_property_suffix(strip_type_suffix(type_name)), local_prefix)


def parse_attributes(xsd_path: Path, local_prefix: str | None) -> dict[str, list[dict]]:
    """Map each complexType's XSD name to its attribute list."""
    root = ET.parse(xsd_path).getroot()
    default_uri = default_namespace(xsd_path)
    attributes = {}
    for ct in root.findall(f"{XSD_NS}complexType"):
        xsd_name = ct.get("name")
        if not xsd_name:
            continue
        # Elements nested inside another element (anonymous inline types)
        # belong to that element, not directly to this complexType.
        parent_of = {child: parent for parent in ct.iter() for child in parent}
        attrs = []
        for el in ct.iter(f"{XSD_NS}element"):
            ancestor = parent_of.get(el)
            nested = False
            while ancestor is not None and ancestor is not ct:
                if ancestor.tag == f"{XSD_NS}element":
                    nested = True
                    break
                ancestor = parent_of.get(ancestor)
            if nested:
                continue
            ref = el.get("ref")
            name = el.get("name")
            occurs = {
                "min": el.get("minOccurs", "1"),
                "max": el.get("maxOccurs", "1"),
            }
            if ref:
                attrs.append({
                    "name": ref.partition(":")[2],
                    "type": format_type(ref, local_prefix, default_uri),
                    **occurs,
                })
            elif name:
                type_name = el.get("type")
                if type_name is None:
                    # Anonymous inline type: use the reference it wraps, if any.
                    inner = el.find(f".//{XSD_NS}element")
                    if inner is not None and inner.get("ref"):
                        type_name = inner.get("ref")
                attrs.append({
                    "name": name,
                    "type": format_type(type_name, local_prefix, default_uri) if type_name else "anonymous",
                    **occurs,
                })
        attributes[xsd_name] = attrs
    return attributes


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
                lines.append(f'  {name} : {attr["type"]}')
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
    lines += ["", generation_footer(), "@enduml", ""]
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
          f"{total} attributes written to {out_path}")


if __name__ == "__main__":
    main()
