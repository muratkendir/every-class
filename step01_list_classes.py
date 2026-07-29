"""Step 01: List all classes from an XSD file as a PlantUML class diagram.

Reads an XML Schema file and treats every top-level named <complexType>
as a UML class. The XSD encoding suffix "Type" is removed from the
displayed class name (the original name is kept as a backup attribute).
Every class name is prefixed with the schema's own namespace prefix
(e.g. "core:") and wrapped in quotes, so that PlantUML files from
different schemas can be combined without name clashes.
Types from other namespaces (GML, XLink, ...) are not resolved yet.

Usage:
    python3 step01_list_classes.py [xsd_path] [output_path]
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

DEFAULT_XSD = Path("schemas/xsds/citygml/3.0/core.xsd")


def strip_type_suffix(name: str) -> str:
    """Remove the XSD encoding suffix "Type" from a type name."""
    return name[:-4] if name.endswith("Type") else name


def strip_property_suffix(name: str) -> str:
    """Remove the XSD encoding suffix "Property" from a type name."""
    return name[:-8] if name.endswith("Property") else name


def parse_classes(xsd_path: Path) -> list[dict]:
    """Return all top-level named complexTypes from the schema.

    Each entry keeps the original XSD name in "xsd_name" as a backup,
    while "name" holds the UML display name with the "Type" suffix removed.
    """
    root = ET.parse(xsd_path).getroot()
    classes = []
    for ct in root.findall(f"{XSD_NS}complexType"):
        name = ct.get("name")
        if name:
            classes.append({
                "name": strip_type_suffix(name),
                "xsd_name": name,
                "abstract": ct.get("abstract") == "true",
            })
    return classes


def schema_prefix(xsd_path: Path) -> str | None:
    """The namespace prefix mapped to the schema's own target namespace."""
    ns_map = {}
    for event, (prefix, uri) in ET.iterparse(xsd_path, events=["start-ns"]):
        ns_map[prefix] = uri
    target_ns = ET.parse(xsd_path).getroot().get("targetNamespace")
    for prefix, uri in ns_map.items():
        if prefix and uri == target_ns:
            return prefix
    return None


def qualify(name: str, prefix: str | None) -> str:
    """Add the schema prefix to a local type name."""
    return f"{prefix}:{name}" if prefix else name


NAME_MAP = {"citygml": "CityGML", "gml": "GML", "indoorgml": "IndoorGML",
            "infragml": "InfraGML", "kml": "KML", "pipelineml": "PipelineML",
            "xlink": "XLink", "filter": "Filter", "georss": "GeoRSS"}


def model_version(xsd_path: Path) -> tuple[str | None, str | None]:
    """(family, version) directory names of the schema path, e.g.
    ("citygml", "3.0"). Handles both flat (schemas/citygml/3.0/core.xsd)
    and nested module layouts (schemas/citygml/construction/3.0/
    construction.xsd): the family name is the nearest ancestor directory
    that is neither the module name nor the version directory."""
    module = xsd_path.stem
    ancestors = [p.name for p in xsd_path.parents]
    version = next((a for a in ancestors if re.fullmatch(r"\d+(\.\d+)*", a)), None)
    family = next((a for a in ancestors
                   if a != version and a.lower() != module.lower() and a != "schemas"), None)
    return family, version


def diagram_title(xsd_path: Path) -> str:
    """Human-readable diagram title derived from the schema path,
    e.g. 'CityGML - 3.0 - Core - Only XSD based'."""
    family, version = model_version(xsd_path)
    parts = [p for p in (family, version, xsd_path.stem) if p]
    label = " - ".join(NAME_MAP.get(p.lower(), p.capitalize()) for p in parts)
    return f"{label} - Only XSD based"


OUTPUT_ROOT = Path("docs") / "output"


def default_output(xsd_path: Path) -> Path:
    """Default output file, so several data models can live side by side:
    docs/output/<DataModelName>/<Version>/UMLClassDiagram/<module>.puml
    (module = schema file stem, lowercased)."""
    family, version = model_version(xsd_path)
    model = NAME_MAP.get((family or "").lower(), (family or "Model").capitalize())
    parts = [OUTPUT_ROOT, model]
    if version:
        parts.append(version)
    parts.append("UMLClassDiagram")
    return Path(*parts) / f"{xsd_path.stem.lower()}.puml"


def target_namespace(xsd_path: Path) -> str | None:
    """The schema's target namespace URI (used as diagram sub-header)."""
    return ET.parse(xsd_path).getroot().get("targetNamespace")


def to_plantuml(classes: list[dict], title: str, prefix: str | None,
                subtitle: str | None = None) -> str:
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
    if any(c["name"].startswith("ADEOf") for c in classes):
        lines += ["", "' ADE hook classes are removed from rendering by default;",
                  "' remove the next line to show them.", "remove $adeOf"]
    if any(c["name"].endswith("Property") for c in classes):
        lines += ["", "' Property pseudo-classes are removed from rendering by default;",
                  "' remove the next line to show them.", "remove $property"]
    lines += ["", "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    xsd_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XSD
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output(xsd_path)

    classes = parse_classes(xsd_path)
    prefix = schema_prefix(xsd_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_plantuml(classes, diagram_title(xsd_path), prefix,
                                    target_namespace(xsd_path)), encoding="utf-8")
    print(f"{len(classes)} classes written to {out_path}")


if __name__ == "__main__":
    main()
