"""Step 08: Expose enumeration values as members of the enum class boxes.

Simple types stamped <<Enumeration>> (step 06) get their allowed values
from the XSD <enumeration> facets rendered as members of the class box.

Usage:
    python3 step08_enumerations.py [xsd_path] [output_path]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from step01_list_classes import XSD_NS, default_output, diagram_title, parse_classes, qualify, schema_prefix, strip_type_suffix, target_namespace
from step02_inheritance import parse_inheritance
from step03_attributes import parse_attributes
from step04_cardinality import multiplicity
from step05_relations import ARROWS, parse_relations
from step06_stereotypes import build_graph, class_stereotypes, parse_simple_types

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")


def parse_union_groups(xsd_path: Path) -> list[dict]:
    """Top-level <group> declarations as «Union» classes."""
    root = ET.parse(xsd_path).getroot()
    result = []
    for grp in root.findall(f"{XSD_NS}group"):
        name = grp.get("name")
        if name:
            if name.endswith("Group"):
                name = name[:-5]
            result.append({"name": name, "stereotype": "Union"})
    return result


def to_plantuml(classes, inheritance, attributes, relations, promoted,
                stereotypes, simple_types, union_groups, title, prefix, subtitle=None):
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
    # FeatureType -> DataType relations are not drawn as relations when the
    # DataType target is concrete; they become private members (- ) of the
    # owning class, hideable via "hide private members". Relations to
    # abstract DataTypes (e.g. placeholders for other modules) stay arrows.
    abstracts = {qualify(c["name"], prefix) for c in classes if c["abstract"]}
    member_rels, drawn_rels = {}, []
    for rel in relations:
        owner_q = qualify(strip_type_suffix(rel["owner"]), prefix)
        if (stereotypes.get(owner_q) == "FeatureType"
                and stereotypes.get(rel["target"]) == "DataType"
                and rel["target"] not in abstracts):
            member_rels.setdefault(rel["owner"], []).append(rel)
        else:
            drawn_rels.append(rel)
    if prefix:
        lines.append(f"package {prefix} {{")
    for cls in classes:
        keyword = "abstract class" if cls["abstract"] else "class"
        line = f'{keyword} "{qualify(cls["name"], prefix)}"'
        pseudo = cls["name"].startswith("ADEOf") or cls["name"].endswith("Property")
        stereotype = stereotypes.get(qualify(cls["name"], prefix))
        if stereotype and not pseudo:
            line += f" <<{stereotype}>>"
        if cls["name"].endswith("Property"):
            line += " $property"
        if cls["name"].startswith("ADEOf"):
            line += " $adeOf"
        attrs = [a for a in attributes.get(cls["xsd_name"], [])
                 if (cls["xsd_name"], a["name"]) not in promoted]
        extra = member_rels.get(cls["xsd_name"], [])
        if attrs or extra:
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
            for rel in extra:
                # Relation to a DataType, shown as a private member instead.
                card = f' [{rel["card"]}]' if rel["card"] != "1" else ""
                lines.append(f'  - {rel["name"]} : {rel["target"]}{card}')
            lines.append("}")
        else:
            lines.append(line)
    if simple_types:
        lines.append("")
        lines.append("' Simple types (from <simpleType> declarations)")
        for st in simple_types:
            decl = f'class "{qualify(st["name"], prefix)}" <<{st["stereotype"]}>>'
            if st["values"]:
                # <<Enumeration>> values from the XSD enumeration facets.
                lines.append(decl + " {")
                for value in st["values"]:
                    lines.append(f"  {value}")
                lines.append("}")
            else:
                lines.append(decl)
    if union_groups:
        lines.append("")
        lines.append("' Model groups (from <group> declarations)")
        for grp in union_groups:
            lines.append(f'class "{qualify(grp["name"], prefix)}" <<{grp["stereotype"]}>>')
    if prefix:
        lines.append("}")
    local_names = {qualify(k, prefix) for k in known}
    stubs = sorted(({q(p) for _, p in inheritance}
                    | {r["target"] for r in relations}) - local_names)
    if stubs:
        lines.append("")
        lines.append("' External types (unresolved namespaces)")
        for stub in stubs:
            keyword = "abstract class" if stub.split(":")[-1].startswith("Abstract") else "class"
            lines.append(f'{keyword} "{stub}"')
    lines.append("")
    for child, parent in inheritance:
        lines.append(f'"{q(parent)}" <|-- "{q(child)}"')
    if drawn_rels:
        lines.append("")
        lines.append("' Class relations (promoted from property wrappers)")
        for rel in drawn_rels:
            # The source-end cardinality is only labeled for composition:
            # by-value containment implies exactly one parent (XML tree
            # semantics). For by-reference relations it is not derivable
            # from the XSD and stays unlabeled.
            source = f' "{rel["source"]}"' if rel["source"] else ""
            lines.append(f'"{q(rel["owner"])}"{source} {ARROWS[rel["kind"]]} '
                         f'"{rel["card"]}" "{rel["target"]}" : {rel["name"]}')
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
    inheritance = parse_inheritance(xsd_path)
    attributes = parse_attributes(xsd_path, prefix)
    known = {qualify(c["name"], prefix) for c in classes}
    graph = build_graph(xsd_path, prefix, inheritance)
    relations, promoted = parse_relations(xsd_path, prefix, inheritance, known, graph)
    stereotypes = class_stereotypes(classes, graph, prefix)
    simple_types = parse_simple_types(xsd_path)
    union_groups = parse_union_groups(xsd_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        to_plantuml(classes, inheritance, attributes, relations, promoted,
                    stereotypes, simple_types, union_groups, diagram_title(xsd_path), prefix,
                    target_namespace(xsd_path)),
        encoding="utf-8")
    print(f"{len(union_groups)} union groups, {len(relations)} class relations "
          f"written to {out_path}")


if __name__ == "__main__":
    main()
