"""Generate one virtual MkDocs page per PlantUML diagram at build time.

Scans docs/output/<DataModel>/<Version>/UMLClassDiagram/*.puml and, for
each file, generates a page
    <section>/<DataModel>-<Version>/<name>.md
that embeds the full PlantUML source in a ```puml fence (rendered inline
by the mkdocs_puml plugin against a PlantUML server) and links the .puml
file. Compilation diagrams from the UMLClassDiagram/compilations/
subdirectory (step 10) get pages under compilations/<Model>-<Version>/
and a "Compilations" sub-entry in the nav below their model-version.
`!include` lines (used by all_packages.puml) are inlined, since the
server cannot resolve files that only exist locally.

The tree nav (Class Diagrams / <Model> <Version> / <name> for the
featured models, Others / <Model> <Version> / <name> for the rest) is
written to SUMMARY.md, consumed by the literate-nav plugin (see
mkdocs.yml).
"""

import re
from pathlib import Path

import mkdocs_gen_files

DOCS_DIR = Path("docs")
PUML_GLOB = "output/*/*/UMLClassDiagram/*.puml"
COMPILATION_GLOB = "output/*/*/UMLClassDiagram/compilations/*.puml"

# Featured model-versions, listed directly under "Class Diagrams" in this
# order; everything else goes under "Others".
FEATURED = [("CityGML", "3.0"), ("GML", "3.2.1"), ("IndoorGML", "1.1")]

INCLUDE_RE = re.compile(r"!include\s+(\S+)")


def puml_source(puml: Path) -> str:
    """The diagram text with `!include` lines replaced by file contents.

    Included files contribute their bodies only (@startuml/@enduml
    stripped); their own title/footer lines stay in place, so the
    including file's later title and footer win — exactly as with
    PlantUML's native !include processing.

    A `skinparam backgroundColor transparent` line is appended before
    `@enduml` so the diagram blends into the page background in both
    light and dark mode. Placed last, it wins over the theme `!include`
    that mkdocs_puml injects right after `@startuml`.
    """
    lines = []
    for line in puml.read_text(encoding="utf-8").splitlines():
        m = INCLUDE_RE.match(line.strip())
        if m:
            included = (puml.parent / m.group(1)).read_text(encoding="utf-8")
            lines.extend(l for l in included.splitlines()
                         if l.strip() not in ("@startuml", "@enduml"))
        else:
            lines.append(line)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "@enduml":
            lines.insert(i, "skinparam backgroundColor transparent")
            break
    else:
        lines.append("skinparam backgroundColor transparent")
    return "\n".join(lines)


nav = mkdocs_gen_files.Nav()
nav["Home"] = "index.md"

diagrams = {}
for puml in sorted(DOCS_DIR.glob(PUML_GLOB)):
    diagrams.setdefault((puml.parts[2], puml.parts[3]), []).append(puml)

others = sorted(mv for mv in diagrams if mv not in FEATURED)
for section, keys in (("Class Diagrams", FEATURED), ("Others", others)):
    for model, version in keys:
        for puml in diagrams.get((model, version), []):
            name = puml.stem
            page = (Path(section.lower().replace(" ", "-"))
                    / f"{model}-{version}" / f"{name}.md")
            # Relative path from the virtual page to the real .puml file
            # (the page lives two levels below the docs root).
            diagram_dir = Path("../../output") / model / version / "UMLClassDiagram"
            with mkdocs_gen_files.open(page, "w") as f:
                f.write(f"# {model} {version} — {name}\n\n")
                f.write(f"```puml\n{puml_source(puml)}\n```\n\n")
                f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})\n")
            nav[section, f"{model} {version}", name] = page.as_posix()

# Compilations (step 10): user-selected module subsets living in the
# UMLClassDiagram/compilations/ subdirectory of a model-version. Same
# page shape as the module diagrams; the pages live under
# compilations/<Model>-<Version>/ (two levels deep, like the module
# pages) and the nav gets a "Compilations" sub-entry under the owning
# model-version, in the same section (Class Diagrams / Others) it
# lives in.
compilations = {}
for puml in sorted(DOCS_DIR.glob(COMPILATION_GLOB)):
    compilations.setdefault((puml.parts[2], puml.parts[3]), []).append(puml)

for (model, version), pumls in compilations.items():
    section = ("Class Diagrams" if (model, version) in FEATURED
               else "Others")
    for puml in pumls:
        name = puml.stem
        page = Path("compilations") / f"{model}-{version}" / f"{name}.md"
        # Relative path from the virtual page to the real diagram
        # directory (same depth as the module pages).
        diagram_dir = Path("../..") / "output" / model / version \
            / "UMLClassDiagram" / "compilations"
        with mkdocs_gen_files.open(page, "w") as f:
            f.write(f"# {model} {version} — Compilation: {name}\n\n")
            f.write(f"```puml\n{puml_source(puml)}\n```\n\n")
            f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})")
            svg = puml.with_suffix(".svg")
            if svg.exists():
                f.write(f" · [SVG: {svg.name}]({diagram_dir}/{svg.name})")
            f.write("\n")
        nav[section, f"{model} {version}", "Compilations", name] = \
            page.as_posix()

with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
    f.writelines(nav.build_literate_nav())
