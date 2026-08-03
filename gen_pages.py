"""Generate one virtual MkDocs page per PlantUML diagram at build time.

Scans docs/output/<DataModel>/<Version>/UMLClassDiagram/*.puml and, for
each file, generates a page
    <DataModel>-<Version>/ClassDiagrams/<name>.md
that embeds the full PlantUML source in a ```puml fence (rendered inline
by the mkdocs_puml plugin against a PlantUML server) and links the .puml
file. `!include` lines (used by all_packages.puml) are inlined, since the
server cannot resolve files that only exist locally.

The tree nav (DataModel-Version / ClassDiagrams / <name>) is written to
SUMMARY.md, consumed by the literate-nav plugin (see mkdocs.yml).
"""

import re
from pathlib import Path

import mkdocs_gen_files

DOCS_DIR = Path("docs")
PUML_GLOB = "output/*/*/UMLClassDiagram/*.puml"

INCLUDE_RE = re.compile(r"!include\s+(\S+)")


def puml_source(puml: Path) -> str:
    """The diagram text with `!include` lines replaced by file contents.

    Included files contribute their bodies only (@startuml/@enduml
    stripped); their own title/footer lines stay in place, so the
    including file's later title and footer win — exactly as with
    PlantUML's native !include processing.
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
    return "\n".join(lines)


nav = mkdocs_gen_files.Nav()
nav["Home"] = "index.md"

for puml in sorted(DOCS_DIR.glob(PUML_GLOB)):
    model, version = puml.parts[2], puml.parts[3]
    name = puml.stem
    page = Path(f"{model}-{version}") / "ClassDiagrams" / f"{name}.md"
    # Relative path from the virtual page to the real .puml file (the
    # page lives two levels below the docs root).
    diagram_dir = Path("../../output") / model / version / "UMLClassDiagram"
    with mkdocs_gen_files.open(page, "w") as f:
        f.write(f"# {model} {version} — {name}\n\n")
        f.write(f"```puml\n{puml_source(puml)}\n```\n\n")
        f.write(f"[PlantUML source: {puml.name}]({diagram_dir}/{puml.name})\n")
    nav[f"{model}-{version}", "ClassDiagrams", name] = page.as_posix()

with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
    f.writelines(nav.build_literate_nav())
