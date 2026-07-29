"""Generate one virtual MkDocs page per PlantUML diagram at build time.

Scans docs/output/<DataModel>/<Version>/UMLClassDiagram/*.puml and, for
each file, generates a page
    <DataModel>-<Version>/ClassDiagrams/<name>.md
that embeds the SVG rendered by the build_plantuml plugin
(out/<name>.svg) and links the .puml source. Nothing is copied: pages
reference the existing files in docs/output/.

The tree nav (DataModel-Version / ClassDiagrams / <name>) is written to
SUMMARY.md, consumed by the literate-nav plugin (see mkdocs.yml).
"""

from pathlib import Path

import mkdocs_gen_files

DOCS_DIR = Path("docs")
PUML_GLOB = "output/*/*/UMLClassDiagram/*.puml"

nav = mkdocs_gen_files.Nav()
nav["Home"] = "index.md"

for puml in sorted(DOCS_DIR.glob(PUML_GLOB)):
    model, version = puml.parts[2], puml.parts[3]
    name = puml.stem
    page = Path(f"{model}-{version}") / "ClassDiagrams" / f"{name}.md"
    # Relative paths from the virtual page to the real files (the page
    # lives two levels below the docs root).
    diagram_dir = Path("../../output") / model / version / "UMLClassDiagram"
    with mkdocs_gen_files.open(page, "w") as f:
        f.write(f"# {model} {version} — {name}\n\n")
        f.write(f"![{name}]({diagram_dir}/out/{name}.svg)\n\n")
        f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})\n")
    nav[f"{model}-{version}", "ClassDiagrams", name] = page.as_posix()

with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
    f.writelines(nav.build_literate_nav())
