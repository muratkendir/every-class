"""Step 09: combine all module diagrams into a single PlantUML file.

The combined file pulls every module .puml in the output directory
together via !include directives and carries the title
"CityGML - 3.0 - All Packages as Single Diagram".

PlantUML 1.2020.02 quirks this file works around (all verified locally):
- quoted class names are global entities, so modules merge cleanly;
- package membership is decided by the FIRST declaration: if a module's
  external stub (a class declared outside the package block, not defined
  by that module's own XSD) is seen before the owning module's real
  declaration, the class is stranded outside its package. Modules are
  therefore included owner-first (topological order over "stubs a class
  owned by another module");
- a later declaration's stereotype REPLACES the earlier one, but a
  redeclaration WITHOUT stereotype never clears it. Stubs carry no
  stereotype, so the real stereotypes survive the merge untouched;
- title blocks of included files clobber the including file's title, so
  the combined title comes AFTER the includes.

Layout: the combined file sets `left to right direction` (portrait —
the default spreads ~19000 px wide) and adds a tree-like layering
bias. PlantUML has no absolute positioning, and core must stay near
the top (generalization ranks force it — a core-at-bottom arrangement
contradicts every generalization edge). For each other module, step 09
counts its direct connections to core (lines referencing `core:` in
its .puml) and links it to core via a hidden package-to-package link
whose dash count (= Graphviz minlen) grows with decreasing
connectivity (`CENTER_PACKAGE` = "core"). Modules with equal
connection counts share a layer; distinct counts are compressed into
~sqrt(n) layers. Note this is a weak hint: the real edges dominate
ranking, so the vertical module order follows the layers only loosely
(measured; see AGENTS.md). The links DO keep core at the top — without
them it lands mid-diagram. Class-level hidden links were tried and
crash Graphviz/smetana on this diagram size.

Stub detection is structural, not stereotype-based: in every module file
the real classes are declared inside the `package <prefix> { ... }`
block and external stubs are the only class declarations outside it.

Run with no arguments: scans docs/output/CityGML/3.0/UMLClassDiagram/ and
writes all_packages.puml there. Render from inside that directory
(includes are basename-relative), as with the per-module files.

Usage:
    python3 step09_all_packages.py [scan_dir] [output_path] [center_package]
    (center_package defaults to CENTER_PACKAGE; every_class.py passes the
    detected/designated core schema's package prefix here.)
"""

import math
import re
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DIR = Path("docs/output/CityGML/3.0/UMLClassDiagram")

DECL_RE = re.compile(r'^(abstract class|class) "([^"]+)"(?: <<([^>]+)>>)?')
TITLE_LINE_RE = re.compile(r"^  (.+)$")
PACKAGE_RE = re.compile(r"^package (\w+) \{")

CENTER_PACKAGE = "core"


def parse_module(path: Path) -> dict:
    """Extract real (in-package) and stub (out-of-package) class
    declarations plus the title's first line from a module .puml file."""
    real, stubs, title_first, package = {}, [], None, None
    in_title = False
    depth = 0  # brace depth: 1 = directly inside the package block
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "title":
            in_title = True
            continue
        if line == "end title":
            in_title = False
            continue
        if in_title:
            m = TITLE_LINE_RE.match(line)
            if m and title_first is None:
                title_first = m.group(1)
            continue
        p = PACKAGE_RE.match(line)
        if p and package is None:
            package = p.group(1)
        m = DECL_RE.match(line)
        if m:
            keyword, name, stereotype = m.groups()
            if depth == 0:  # outside the package block: external stub
                stubs.append(name)
            elif depth == 1 and "$" not in line:  # skip $property/$adeOf
                real[name] = (keyword, stereotype)
        depth += line.count("{") - line.count("}")
    return {"real": real, "stubs": stubs, "title": title_first,
            "package": package}

def include_order(modules: dict[str, dict]) -> list[str]:
    """Owners before stubbers: a module that declares a class as an
    external stub is included after the module owning that class, so
    package membership is set by the real declaration."""
    owner = {cls: mod for mod, m in modules.items() for cls in m["real"]}
    deps = {mod: {owner[c] for c in m["stubs"]
                  if c in owner and owner[c] != mod}
            for mod, m in modules.items()}
    order, remaining = [], dict(sorted(deps.items()))
    while remaining:
        ready = [mod for mod, d in remaining.items() if not d & remaining.keys()]
        if not ready:  # cycle: fall back to alphabetical
            ready = [next(iter(remaining))]
        order.extend(ready)
        for mod in ready:
            del remaining[mod]
    return order


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else out_dir / "all_packages.puml"
    center = sys.argv[3] if len(sys.argv) > 3 else CENTER_PACKAGE

    paths = sorted(p for p in out_dir.glob("*.puml") if p != out_path)
    modules = {p.name: parse_module(p) for p in paths}
    order = include_order(modules)

    # Diagram title: "<model> - <version>" from any module's title
    # ("CityGML - 3.0 - Core - Only XSD based" -> "CityGML - 3.0").
    first_title = next((m["title"] for m in modules.values() if m["title"]), "")
    base = " - ".join(first_title.split(" - ")[:2])
    title = f"{base} - All Packages as Single Diagram"

    lines = ["@startuml",
             "' Generated by step09_all_packages.py - do not edit.",
             "' Combines all module diagrams via includes."]
    lines += [f"!include {name}" for name in order]

    # Portrait orientation: rotate the layout 90 degrees so the diagram
    # stacks up-to-down instead of spreading landscape-wide. Inheritance
    # flows left-to-right, so core sits at the LEFT edge and the
    # connectivity layers (below) extend rightward; the wide same-rank
    # class rows become vertical extent.
    lines += ["", "left to right direction"]

    # Layout bias: tree-like layering away from the central package.
    # For each other module, count its direct connections to core
    # (lines referencing `core:` in its .puml: attributes typed with
    # core types, external stub declarations, inheritance/relation
    # edges to core classes). Each module is then tied to core via a
    # hidden package-to-package link whose dash count (= Graphviz
    # minlen) grows per layer: most-connected modules sit closest to
    # core, least-connected at the far fringe. Modules with equal
    # connection counts always share a layer. Distinct counts are
    # compressed into ~sqrt(n) layers. The links also keep core near
    # the top of the portrait layout — without them it drifts to the
    # middle (measured; see AGENTS.md).
    center_prefix = center + ":"
    packages = {modules[name]["package"] for name in order} - {None}
    counts = {}
    for name in order:
        pkg = modules[name]["package"]
        if pkg and pkg != center:
            text = (out_dir / name).read_text(encoding="utf-8")
            counts[pkg] = sum(center_prefix in line
                              for line in text.splitlines())
    if center in packages and counts:
        distinct = sorted(set(counts.values()), reverse=True)
        n_layers = max(1, round(math.sqrt(len(counts))))
        layer = {c: 1 + i * n_layers // len(distinct)
                 for i, c in enumerate(distinct)}
        lines += ["", "' hidden links: tree-like layering away from the",
                  "' central package (dash count = distance from core,",
                  "' layer assigned by decreasing core-connection count)"]
        for c in distinct:
            pkgs = sorted(p for p in counts if counts[p] == c)
            lines += [f"' layer {layer[c]} ({c} connections to core): "
                      f"{', '.join(pkgs)}"]
            dashes = "-" * layer[c]
            lines += [f"{center} -[hidden]{dashes}- {p}"
                      for p in pkgs]

    lines += ["", "title", f"  {title}", "end title"]
    lines += ["", f"footer Generated on {datetime.now():%Y-%m-%d %H:%M:%S}",
              "@enduml", ""]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(order)} modules included, written to {out_path}")


if __name__ == "__main__":
    main()
