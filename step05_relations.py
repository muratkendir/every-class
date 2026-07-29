"""Step 05: Expose relations (composition, aggregation, dependency).

Attributes that reference other classes through the GML property pattern
are promoted from the attribute compartment to UML relations:

- by-value property wrapper (no gml:AssociationAttributeGroup)
  -> composition, source cardinality "1" (guaranteed by XML tree
     semantics: a contained element has exactly one parent)
- by-reference wrapper (gml:AssociationAttributeGroup present)
  -> aggregation if the target is a Feature (descends from
     gml:AbstractFeature), dependency otherwise; source cardinality
     left unlabeled (not derivable from the XSD)
- gml:ReferenceType attributes and by-reference anonymous wrappers
  without an inner element ref (e.g. extending
  gml:AbstractFeatureMemberType)
  -> target taken from <appinfo><targetElement>; ReferenceType always
     yields a dependency, anonymous wrappers follow the by-reference
     rule above. Such targets may live in another module; they are
     drawn as <<external>> stub classes.

The target-end cardinality comes from the attribute's min/maxOccurs.
Promoted attributes are removed from the class body. <group ref="...">
usages (e.g. CityModelMemberGroup) are expanded as if their members were
declared inline. By-value/inner-ref targets outside the schema still
stay attributes. Realization is reserved but not produced (no interfaces
in the schema).

Usage:
    python3 step05_relations.py [xsd_path] [output_path]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from step01_list_classes import XSD_NS, default_output, diagram_title, parse_classes, qualify, schema_prefix, strip_type_suffix, target_namespace
from step02_inheritance import build_graph, parse_inheritance
from step03_attributes import parse_attributes
from step04_cardinality import multiplicity

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")

GML_NS = "{http://www.opengis.net/gml/3.2}"

ARROWS = {"composition": "*--", "aggregation": "o--", "dependency": "..>"}


def occurs_card(el) -> str:
    lo = el.get("minOccurs", "1")
    hi = el.get("maxOccurs", "1")
    hi = "*" if hi == "unbounded" else hi
    return lo if lo == hi else f"{lo}..{hi}"


def direct_elements(ct):
    """Direct child <element> nodes of a complexType (not nested in others)."""
    parent_of = {child: parent for parent in ct.iter() for child in parent}
    for el in ct.iter(f"{XSD_NS}element"):
        ancestor = parent_of.get(el)
        nested = False
        while ancestor is not None and ancestor is not ct:
            if ancestor.tag == f"{XSD_NS}element":
                nested = True
                break
            ancestor = parent_of.get(ancestor)
        if not nested:
            yield el


def direct_group_refs(ct):
    """Direct child <group> reference nodes of a complexType."""
    parent_of = {child: parent for parent in ct.iter() for child in parent}
    for grp in ct.iter(f"{XSD_NS}group"):
        ancestor = parent_of.get(grp)
        nested = False
        while ancestor is not None and ancestor is not ct:
            if ancestor.tag in (f"{XSD_NS}element", f"{XSD_NS}group"):
                nested = True
                break
            ancestor = parent_of.get(ancestor)
        if not nested:
            yield grp


def parse_relations(xsd_path, local_prefix, inheritance, known, graph=None):
    """Extract class-to-class relations from property wrappers.

    Returns (relations, promoted) where promoted is a set of
    (owner_xsd_name, attribute_name) pairs to drop from class bodies.
    `graph` is an optional cross-module child->parent map (see step02's
    build_graph); without it, only this module's inheritance is used for
    the Feature check.
    """
    root = ET.parse(xsd_path).getroot()
    ctypes = {ct.get("name"): ct for ct in root.findall(f"{XSD_NS}complexType") if ct.get("name")}

    if graph is None:
        graph = {}
        for child, parent in inheritance:
            p = strip_type_suffix(parent)
            graph[qualify(strip_type_suffix(child), local_prefix)] = \
                qualify(p, local_prefix) if ":" not in p else p
    child_to_parent = graph

    def is_feature(qname) -> bool:
        cur, seen = qname, set()
        while cur in child_to_parent and cur not in seen:
            seen.add(cur)
            cur = child_to_parent[cur]
            if cur == "gml:AbstractFeature":
                return True
        return False

    groups = {g.get("name"): g for g in root.findall(f"{XSD_NS}group") if g.get("name")}

    relations, promoted = [], set()

    def add_wrapper_relation(owner, name, wrapper, card, el=None):
        by_ref = any(ag.get("ref") == "gml:AssociationAttributeGroup"
                     for ag in wrapper.iter(f"{XSD_NS}attributeGroup"))
        inner = wrapper.find(f".//{XSD_NS}element")
        target = None
        if inner is not None and inner.get("ref"):
            rp, _, rl = inner.get("ref").partition(":")
            t = qualify(strip_type_suffix(rl), local_prefix) if rp == local_prefix else None
            if t is not None and t in known:
                target = t
            # inner-ref targets outside this schema: keep as attribute
        if target is None and by_ref and el is not None:
            # By-reference wrapper without an inner element ref (e.g.
            # extending gml:AbstractFeatureMemberType): the target comes
            # from <appinfo><targetElement> and may be external.
            te = el.find(f".//{GML_NS}targetElement")
            if te is not None and te.text:
                target = strip_type_suffix(te.text.strip())
                if ":" not in target:
                    target = qualify(target, local_prefix)
        if target is None:
            return
        if not by_ref:
            kind, source = "composition", "1"
        elif is_feature(target):
            kind, source = "aggregation", ""
        else:
            kind, source = "dependency", ""
        relations.append({
            "owner": owner, "name": name, "target": target,
            "kind": kind, "source": source, "card": card,
        })
        promoted.add((owner, name))

    for ct in root.findall(f"{XSD_NS}complexType"):
        owner = ct.get("name")
        if not owner:
            continue
        for el in direct_elements(ct):
            name = el.get("name")
            if not name or name.startswith("adeOf"):
                continue
            type_name = el.get("type")
            wrapper = None
            if type_name:
                p, sep, loc = type_name.partition(":")
                if sep and p == local_prefix and loc.endswith("PropertyType"):
                    wrapper = ctypes.get(loc)
                elif sep and p == "gml" and loc == "ReferenceType":
                    # Weak reference; target from <appinfo><targetElement>,
                    # may live in another module (drawn as external stub).
                    te = el.find(f".//{GML_NS}targetElement")
                    if te is not None and te.text:
                        target = strip_type_suffix(te.text.strip())
                        if ":" not in target:
                            target = qualify(target, local_prefix)
                        relations.append({
                            "owner": owner, "name": name, "target": target,
                            "kind": "dependency", "source": "",
                            "card": occurs_card(el),
                        })
                        promoted.add((owner, name))
                    continue
                else:
                    continue  # simple/enumeration data type: stays attribute
            else:
                wrapper = el.find(f"{XSD_NS}complexType")
            if wrapper is None:
                continue
            add_wrapper_relation(owner, name, wrapper, occurs_card(el), el)
        # Expand <group ref="..."> usages (e.g. core:CityModelMemberGroup):
        # each member is treated as if declared inline. A <choice> or a
        # minOccurs="0" group makes each member optional; an unbounded
        # group occurrence makes each member unbounded as well.
        for grp in direct_group_refs(ct):
            ref = grp.get("ref")
            if not ref:
                continue
            group_def = groups.get(ref.partition(":")[2])
            if group_def is None:
                continue
            g_lo = grp.get("minOccurs", "1")
            g_hi = grp.get("maxOccurs", "1")
            for tag in ("choice", "sequence"):
                for mel in group_def.findall(f"{XSD_NS}{tag}/{XSD_NS}element"):
                    name = mel.get("name")
                    if not name or name.startswith("adeOf"):
                        continue
                    lo = "0" if g_lo == "0" or tag == "choice" else mel.get("minOccurs", "1")
                    hi = g_hi if g_hi != "1" else mel.get("maxOccurs", "1")
                    hi = "*" if hi == "unbounded" else hi
                    card = lo if lo == hi else f"{lo}..{hi}"
                    wrapper = mel.find(f"{XSD_NS}complexType")
                    if wrapper is not None:
                        add_wrapper_relation(owner, name, wrapper, card, mel)
    return relations, promoted


def to_plantuml(classes, inheritance, attributes, relations, promoted, title, prefix,
                subtitle=None):
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
        attrs = [a for a in attributes.get(cls["xsd_name"], [])
                 if (cls["xsd_name"], a["name"]) not in promoted]
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
    if relations:
        lines.append("")
        lines.append("' Class relations (promoted from property wrappers)")
        for rel in relations:
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
    relations, promoted = parse_relations(xsd_path, prefix, inheritance, known,
                                          build_graph(xsd_path, prefix, inheritance))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        to_plantuml(classes, inheritance, attributes, relations, promoted,
                    diagram_title(xsd_path), prefix, target_namespace(xsd_path)),
        encoding="utf-8")
    by_kind = {k: sum(1 for r in relations if r["kind"] == k) for k in ARROWS}
    counts = ", ".join(f"{n} {k}" for k, n in by_kind.items() if n)
    print(f"{len(classes)} classes, {len(inheritance)} inheritance relations, "
          f"{len(relations)} class relations ({counts}) written to {out_path}")


if __name__ == "__main__":
    main()
