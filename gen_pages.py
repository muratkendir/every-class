"""Generate one virtual MkDocs page per PlantUML diagram at build time.

Scans docs/output/<DataModel>/<Version>/UMLClassDiagram/*.puml and, for
each file, generates a page
    <section>/<DataModel>-<Version>/<name>.md
that embeds the full PlantUML source in a ```puml fence (rendered inline
by the mkdocs_puml plugin against a PlantUML server) and links the .puml
file. Compilation diagrams from the UMLClassDiagram/compilations/
subdirectory (step 10) get pages under compilations/<Model>-<Version>/
and a "Compilations" sub-entry in the nav below their model-version;
Crow's-foot E-R diagrams from the UMLClassDiagram/crowsfoot/
subdirectory (step 11) get pages under crowsfoot/<Model>-<Version>/ and
a "Crow's Foot Diagrams" sub-entry the same way.
`!include` lines (used by all_packages.puml) are inlined, since the
server cannot resolve files that only exist locally.

The tree nav (<Model> <Version> as the top-level entry with the
sub-menus "Class Diagrams" and "Compilations" below it; featured
model-versions first, then the rest alphabetically) is written to
SUMMARY.md, consumed by the literate-nav plugin (see mkdocs.yml).
"""

import re
from pathlib import Path

import mkdocs_gen_files

DOCS_DIR = Path("docs")
PUML_GLOB = "output/*/*/UMLClassDiagram/*.puml"
COMPILATION_GLOB = "output/*/*/UMLClassDiagram/compilations/*.puml"
CROWSFOOT_GLOB = "output/*/*/UMLClassDiagram/crowsfoot/*.puml"

# Featured model-versions, listed first in the nav in this order;
# everything else follows alphabetically.
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

# Compilations (step 10): user-selected module subsets living in the
# UMLClassDiagram/compilations/ subdirectory of a model-version. Same
# page shape as the module diagrams; the pages live under
# compilations/<Model>-<Version>/ (two levels deep, like the module
# pages).
compilations = {}
for puml in sorted(DOCS_DIR.glob(COMPILATION_GLOB)):
    compilations.setdefault((puml.parts[2], puml.parts[3]), []).append(puml)

# Crow's-foot E-R diagrams (step 11): diagrams centered on one class,
# living in the UMLClassDiagram/crowsfoot/ subdirectory of a
# model-version. Same page shape as the compilations; the pages live
# under crowsfoot/<Model>-<Version>/.
crowsfoot = {}
for puml in sorted(DOCS_DIR.glob(CROWSFOOT_GLOB)):
    crowsfoot.setdefault((puml.parts[2], puml.parts[3]), []).append(puml)

# Nav hierarchy (user decision 2026-10-24): the model-version is the
# top-level entry, with sub-menus below it — "Class Diagrams"
# (per-module diagrams incl. all_packages), "Compilations" (step 10
# subset diagrams) and "Crow's Foot Diagrams" (step 11, when
# present).
# FEATURED model-versions come first, the rest follow alphabetically.
# The virtual page PATHS stay at class-diagrams/<Model>-<Version>/,
# compilations/<Model>-<Version>/ and crowsfoot/<Model>-<Version>/
# so
# existing URLs keep working.
others = sorted(mv for mv in set(diagrams) | set(compilations) | set(crowsfoot)
                if mv not in FEATURED)
for model, version in [*FEATURED, *others]:
    for puml in diagrams.get((model, version), []):
        name = puml.stem
        page = Path("class-diagrams") / f"{model}-{version}" / f"{name}.md"
        # Relative path from the virtual page to the real .puml file
        # (the page lives two levels below the docs root).
        diagram_dir = Path("../../output") / model / version / "UMLClassDiagram"
        with mkdocs_gen_files.open(page, "w") as f:
            f.write(f"# {model} {version} — {name}\n\n")
            f.write(f"```puml\n{puml_source(puml)}\n```\n\n")
            f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})\n")
        nav[f"{model} {version}", "Class Diagrams", name] = page.as_posix()
    for puml in compilations.get((model, version), []):
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
        nav[f"{model} {version}", "Compilations", name] = page.as_posix()
    for puml in crowsfoot.get((model, version), []):
        name = puml.stem
        page = Path("crowsfoot") / f"{model}-{version}" / f"{name}.md"
        # Relative path from the virtual page to the real diagram
        # directory (same depth as the module pages).
        diagram_dir = Path("../..") / "output" / model / version \
            / "UMLClassDiagram" / "crowsfoot"
        with mkdocs_gen_files.open(page, "w") as f:
            f.write(f"# {model} {version} — Crow's Foot E-R: {name}\n\n")
            f.write(f"```puml\n{puml_source(puml)}\n```\n\n")
            f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})")
            svg = puml.with_suffix(".svg")
            if svg.exists():
                f.write(f" · [SVG: {svg.name}]({diagram_dir}/{svg.name})")
            f.write("\n")
        nav[f"{model} {version}", "Crow's Foot Diagrams", name] = \
            page.as_posix()

with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
    f.writelines(nav.build_literate_nav())

# Divider between featured and older model-versions in the primary nav
# (user decision 2026-10-24). Generated here so its position always
# matches FEATURED: Home is nav item 1, so the first non-featured model
# is item 2 + <number of featured models actually present>.
present = set(diagrams) | set(compilations)
divider_at = 2 + sum(1 for mv in FEATURED if mv in present)
with mkdocs_gen_files.open("stylesheets/nav-divider.css", "w") as f:
    f.write("/* Generated by gen_pages.py: thin divider before the first\n"
            "   non-featured model-version in the primary nav. */\n"
            ".md-nav--primary > .md-nav__list > "
            f".md-nav__item:nth-child({divider_at}) {{\n"
            "  border-top: 1px solid var(--md-default-fg-color--lighter);\n"
            "  margin-top: .4rem;\n"
            "  padding-top: .4rem;\n"
            "}\n")
