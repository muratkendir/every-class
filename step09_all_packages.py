"""Step 09: combine all module diagrams into a single PlantUML file.

The combined file INLINES every module .puml of the output directory
(deduplicated) and carries the title
"<model> - <version> - All Packages as Single Diagram".

Why inlining instead of `!include`: the combined diagram must declare
each class exactly ONCE. Module diagrams follow the per-module
convention of redeclaring other modules' classes as bare external stubs
(outside their `package` block). Older PlantUML (1.2020.02) merged
duplicate quoted declarations into one box ("package membership sticks
to the first declaration"), so `!include` worked. Current PlantUML
treats packages as namespaces and splits names on ':': a class
"con:X" declared inside `package con` is a DIFFERENT entity from
"con:X" declared outside it (`con.con.X` vs `con.X`) — so stubs never
merged with real classes and arrows ended at stranded stub copies.
Two changes make the combined diagram correct under any PlantUML
version (verified 2026-10-14 against the server of the Jetty 12
image): every class carries a plain-identifier ALIAS
(`class "con:X" as con_X`, see step01.alias_of) immune to namespace
splitting, and step 09 inlines the module sources keeping only the
FIRST declaration of each class (owner-first order). Step 10
(step10_compilation.py) reuses build_combined() for user-selected
subsets ("compilations").

Modules are inlined owner-first (topological order over "stubs a class
owned by another module"), so the kept declaration is the owning
module's real one — with stereotype, body and package membership. Stub
detection is structural, not stereotype-based: in every module file the
real classes are declared inside the `package <prefix> { ... }` block
and external stubs are the only class declarations outside it.

Module title blocks, footers and @start/@enduml markers are stripped;
edges, comments and hide/remove directives pass through (the directives
repeat once per merged module — harmless duplicates).

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

Run with no arguments: scans docs/output/CityGML/3.0/UMLClassDiagram/ and
writes all_packages.puml there.

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

from step01_list_classes import alias_of

DEFAULT_DIR = Path("docs/output/CityGML/3.0/UMLClassDiagram")

DECL_RE = re.compile(r'^(abstract class|class) "([^"]+)"(?: as ([A-Za-z0-9_]+))?')
TITLE_LINE_RE = re.compile(r"^  (.+)$")
PACKAGE_RE = re.compile(r"^package (\w+) \{")
FOOTER_RE = re.compile(r"^footer Generated on ")
STEREO_RE = re.compile(r"<<([^>]+)>>")
ATTR_RE = re.compile(r"^  ([#~+\-]?)\s*(\w+) : (\w+):(\w+)(?: \[([^\]]+)\])?\s*$")

CENTER_PACKAGE = "core"


def decl_key(match: re.Match) -> str:
    """Identity of a class declaration: its `as` alias, falling back to
    the (prefixed) display name."""
    return match.group(3) or alias_of(match.group(2))


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
            if depth == 0:  # outside the package block: external stub
                stubs.append(decl_key(m))
            elif depth == 1 and "$" not in line:  # skip $property/$adeOf
                real[decl_key(m)] = m.group(1)
        depth += line.count("{") - line.count("}")
    return {"real": real, "stubs": stubs, "title": title_first,
            "package": package}


def include_order(modules: dict[str, dict]) -> list[str]:
    """Owners before stubbers: a module that declares a class as an
    external stub comes after the module owning that class, so the
    kept declaration is the real one (with stereotype and body)."""
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


def strip_frame(lines: list[str]) -> list[str]:
    """Drop the @startuml/@enduml markers, the title block and the
    generation footer of one module file (the combined file sets its
    own)."""
    out, in_title = [], False
    for line in lines:
        s = line.strip()
        if s in ("@startuml", "@enduml"):
            continue
        if s == "title":
            in_title = True
            continue
        if s == "end title":
            in_title = False
            continue
        if in_title or FOOTER_RE.match(line):
            continue
        out.append(line)
    return out


def merge_sources(order: list[str], texts: dict[str, list[str]]) -> list[str]:
    """Inline the module sources, keeping only the FIRST declaration of
    each class (owner-first order ensures it is the real one). Later
    stub redeclarations are dropped together with their body, if any;
    edges and directives pass through untouched. A `' ---- <file> ----`
    marker comment precedes each inlined module."""
    seen: set[str] = set()
    out: list[str] = []
    skip_body = 0
    for name in order:
        out.append(f"' ---- {name} ----")
        for line in texts[name]:
            if skip_body:
                skip_body += line.count("{") - line.count("}")
                skip_body = max(skip_body, 0)
                continue
            m = DECL_RE.match(line)
            if m:
                if decl_key(m) in seen:
                    skip_body = max(line.count("{") - line.count("}"), 0)
                    continue
                seen.add(decl_key(m))
            out.append(line)
    return out


def promote_attribute_relations(lines: list[str]) -> tuple[list[str], int]:
    """Turn attributes whose value type is declared as a class in the
    same combined diagram into relation arrows, and drop them from the
    class bodies. Meant for compilations (step 10), where e.g.
    `bldg:BuildingUnit`'s `# address : core:Address [0..*]` would
    otherwise stay a text attribute although `core:Address` is present
    as a class box.

    Arrow type follows step 05's by-reference rule: the target's
    stereotype decides — «FeatureType» -> aggregation (o--), anything
    else -> dependency (..>). The attribute's [min..max] becomes the
    target-end cardinality label; the source end stays unlabeled.
    `~` (adeOf) and `-` (DataType relations deliberately demoted to
    private members, step 06) members and the bodies of $-tagged
    ($property/$adeOf) classes are left untouched, as are attributes
    whose type is not declared in this diagram (they stay attributes)."""
    stereotypes = {}
    for line in lines:
        m = DECL_RE.match(line)
        if m and "$" not in line:
            s = STEREO_RE.search(line)
            stereotypes[decl_key(m)] = s.group(1) if s else ""
    out, edges = [], []
    body_owner = None  # alias of the class whose body we are in ("" = skip)
    body_depth = depth = 0
    for line in lines:
        if body_owner and depth == body_depth:
            a = ATTR_RE.match(line)
            if a and a.group(1) not in ("~", "-"):
                _, name, prefix, typ, card = a.groups()
                target = alias_of(f"{prefix}:{typ}")
                if target in stereotypes and target != body_owner:
                    arrow = "o--" if stereotypes[target] == "FeatureType" \
                        else "..>"
                    label = f' "{card}"' if card and card != "1" else ""
                    edges.append(f'"{body_owner}" {arrow}{label} '
                                 f'"{target}" : {name}')
                    continue
        m = DECL_RE.match(line)
        new_depth = depth + line.count("{") - line.count("}")
        if m and new_depth > depth:
            body_owner = decl_key(m) if "$" not in line else ""
            body_depth = new_depth
        depth = new_depth
        if depth < body_depth:
            body_owner = None
        out.append(line)
    if not edges:
        return out, 0
    out += ["",
            "' ---- attribute promotions ----",
            "' attributes whose value type is declared in this diagram,",
            "' drawn as relations instead (FeatureType target ->",
            "' aggregation, else dependency; target-end cardinality",
            "' from the XSD occurrence)"] + edges
    return out, len(edges)


def hidden_layer_lines(modules: dict[str, dict], order: list[str],
                       texts: dict[str, list[str]], center: str) -> list[str]:
    """Tree-like layering bias away from the central package: for each
    other module, count its direct connections to `center` (lines
    referencing `center:` in its source: core-typed attributes, stub
    declarations, edges) and tie it to center via a hidden
    package-to-package link whose dash count (= Graphviz minlen) grows
    with decreasing connectivity. Equal counts share a layer; distinct
    counts are compressed into ~sqrt(n) layers. Empty when `center` is
    not among the merged packages."""
    center_prefix = center + ":"
    packages = {modules[name]["package"] for name in order} - {None}
    counts = {}
    for name in order:
        pkg = modules[name]["package"]
        if pkg and pkg != center:
            counts[pkg] = sum(center_prefix in line
                              for line in texts[name])
    if center not in packages or not counts:
        return []
    distinct = sorted(set(counts.values()), reverse=True)
    n_layers = max(1, round(math.sqrt(len(counts))))
    layer = {c: 1 + i * n_layers // len(distinct)
             for i, c in enumerate(distinct)}
    lines = ["", "' hidden links: tree-like layering away from the",
             "' central package (dash count = distance from core,",
             "' layer assigned by decreasing core-connection count)"]
    for c in distinct:
        pkgs = sorted(p for p in counts if counts[p] == c)
        lines += [f"' layer {layer[c]} ({c} connections to core): "
                  f"{', '.join(pkgs)}"]
        dashes = "-" * layer[c]
        lines += [f"{center} -[hidden]{dashes}- {p}" for p in pkgs]
    return lines


def build_combined(modules: dict[str, dict], texts: dict[str, list[str]],
                   order: list[str], title: str, center: str,
                   header: str = "step09_all_packages.py",
                   promote_attrs: bool = False) -> str:
    """Assemble the combined diagram source for `order` modules:
    deduplicated inlines, portrait direction, connectivity-based hidden
    layering, title and footer. With `promote_attrs` (step 10), attributes
    whose value type is declared in the diagram become relation arrows
    (see promote_attribute_relations)."""
    lines = ["@startuml",
             f"' Generated by {header} - do not edit.",
             "' Module stubs inlined away: each class is declared",
             "' exactly once (owner-first), edges kept."]
    merged = merge_sources(order, texts)
    if promote_attrs:
        merged, n_promoted = promote_attribute_relations(merged)
        print(f"promoted {n_promoted} attribute(s) to relations")
    lines += merged

    # Portrait orientation: rotate the layout 90 degrees so the diagram
    # stacks up-to-down instead of spreading landscape-wide. Inheritance
    # flows left-to-right, so core sits at the LEFT edge and the
    # connectivity layers (below) extend rightward; the wide same-rank
    # class rows become vertical extent.
    lines += ["", "left to right direction"]
    lines += hidden_layer_lines(modules, order, texts, center)

    lines += ["", "title", f"  {title}", "end title"]
    lines += ["", f"footer Generated on {datetime.now():%Y-%m-%d %H:%M:%S}",
              "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else out_dir / "all_packages.puml"
    center = sys.argv[3] if len(sys.argv) > 3 else CENTER_PACKAGE

    paths = sorted(p for p in out_dir.glob("*.puml") if p != out_path)
    modules = {p.name: parse_module(p) for p in paths}
    texts = {p.name: strip_frame(p.read_text(encoding="utf-8").splitlines())
             for p in paths}
    order = include_order(modules)

    # Diagram title: "<model> - <version>" from any module's title
    # ("CityGML - 3.0 - Core - Only XSD based" -> "CityGML - 3.0").
    first_title = next((m["title"] for m in modules.values() if m["title"]), "")
    base = " - ".join(first_title.split(" - ")[:2])
    title = f"{base} - All Packages as Single Diagram"

    source = build_combined(modules, texts, order, title, center)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(f"{len(order)} modules merged, written to {out_path}")


if __name__ == "__main__":
    main()
