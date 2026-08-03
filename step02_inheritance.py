"""Step 02: Expose inheritance (generalization) relations between classes.

In XSD, generalization is expressed with <complexContent><extension base="...">
(or <restriction base="...">). Base types from the schema's own namespace are
matched against the local classes; base types from other namespaces (GML,
XLink, ...) are kept as prefixed names and drawn as stub classes.

Usage:
    python3 step02_inheritance.py [xsd_path] [output_path]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from step01_list_classes import XSD_NS, default_output, diagram_title, generation_footer, parse_classes, qualify, schema_prefix, strip_type_suffix, target_namespace

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")


def parse_inheritance(xsd_path: Path) -> list[tuple[str, str]]:
    """Return (child, parent) pairs from extension/restriction elements.

    Parents keep the prefix exactly as written: a same-prefix base is not
    necessarily declared in this XSD (several schema files can share one
    namespace, e.g. the GML modules), so stripping it would produce
    unprefixed stubs for cross-module bases."""
    root = ET.parse(xsd_path).getroot()
    relations = []
    for ct in root.findall(f"{XSD_NS}complexType"):
        child = ct.get("name")
        if not child:
            continue
        for cc in ct.findall(f"{XSD_NS}complexContent"):
            for tag in ("extension", "restriction"):
                for ext in cc.findall(f"{XSD_NS}{tag}"):
                    base = ext.get("base")
                    if not base:
                        continue
                    relations.append((child, base))
    return relations


SEARCH_ROOT = Path("schemas")


def find_schema_by_namespace(namespace: str, search_root: Path | None = None) -> Path | None:
    """Locate a local XSD file by its target namespace.

    Searches SEARCH_ROOT (the whole `schemas/` tree by default;
    every_class.py narrows it to the given schema-set folder, so external
    namespaces are only considered when deliberately stored in that
    folder)."""
    for path in (search_root or SEARCH_ROOT).rglob("*.xsd"):
        if ET.parse(path).getroot().get("targetNamespace") == namespace:
            return path
    return None


def build_graph(xsd_path: Path, prefix: str | None, inheritance) -> dict:
    """Child->parent map for ancestry walks, extended across modules.

    <import> declarations are resolved against local XSD files (by target
    namespace, recursive); imports not found locally (GML, XLink, ...)
    stay external stubs.
    """
    graph = {}

    def add(relations, owner_prefix):
        for child, parent in relations:
            p = strip_type_suffix(parent)
            graph.setdefault(qualify(strip_type_suffix(child), owner_prefix),
                             qualify(p, owner_prefix) if ":" not in p else p)

    add(inheritance, prefix)
    seen = set()

    def visit_imports(path: Path):
        if path in seen:
            return
        seen.add(path)
        root = ET.parse(path).getroot()
        for imp in root.findall(f"{XSD_NS}import"):
            ns = imp.get("namespace")
            resolved = find_schema_by_namespace(ns) if ns else None
            if resolved is None:
                continue  # external namespace (GML, XLink, ...): not followed
            add(parse_inheritance(resolved), schema_prefix(resolved))
            visit_imports(resolved)

    visit_imports(xsd_path)
    return graph


def to_plantuml(classes, relations, title, prefix, subtitle=None):
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
    lines += ["", generation_footer(), "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    xsd_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XSD
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output(xsd_path)

    classes = parse_classes(xsd_path)
    relations = parse_inheritance(xsd_path)
    prefix = schema_prefix(xsd_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_plantuml(classes, relations, diagram_title(xsd_path), prefix,
                                    target_namespace(xsd_path)), encoding="utf-8")
    print(f"{len(classes)} classes, {len(relations)} inheritance relations written to {out_path}")


if __name__ == "__main__":
    main()
