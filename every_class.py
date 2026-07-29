"""every-class: main application.

Given a data-model schema folder (e.g. schemas/xsds/citygml/), which may
hold multiple versions of the same data model, detects the data model,
all available versions and the connected schema files, picks (or asks
for) the core/base schema, then runs the full pipeline: steps 01-08 for
every package (each overwrites the same .puml with a richer diagram, so
the latest step's output is the final one) and step 09 for the combined
all_packages diagram. All PlantUML files land in
output/<DataModel>/<Version>/UMLClassDiagram/.

Detection rules (see AGENTS.md):
- DataModel name = folder name; display name via NAME_MAP
  (citygml -> CityGML), fallback: capitalized folder name.
- Version = nearest ancestor directory matching a version pattern
  (e.g. "3.0", "2.2.0"); every version found in the folder is
  processed, each into its own output folder.
- Every .xsd in the folder becomes one package (module schemas,
  InfraGML parts, bundled external dependencies alike).
- External namespaces are NOT considered unless their schemas are
  deliberately stored in the same folder: <import> resolution (step
  02's SEARCH_ROOT) is scoped to the given folder.
- Core schema resolution order: --core argument; a file named
  core/base/<model>core/<model>base (e.g. core.xsd, cityGMLBase.xsd,
  indoorgmlcore.xsd); the only schema in the version; otherwise the
  user is asked to pick one interactively.
- Processing order is topological over <import> declarations resolved
  against the same version group (dependencies first; cycles fall back
  to alphabetical).

Usage:
    python3 every_class.py <model_folder> [--core <schema_name>]
"""

import argparse
import importlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from step01_list_classes import NAME_MAP, XSD_NS, schema_prefix

VERSION_RE = re.compile(r"\d+(\.\d+)*")

STEP_MODULES = [
    "step01_list_classes",
    "step02_inheritance",
    "step03_attributes",
    "step04_cardinality",
    "step05_relations",
    "step06_stereotypes",
    "step07_groups",
    "step08_enumerations",
]


def schema_info(path: Path) -> tuple[str | None, list[str]]:
    """(targetNamespace, imported namespaces) of one XSD file."""
    root = ET.parse(path).getroot()
    imports = [imp.get("namespace") for imp in root.findall(f"{XSD_NS}import")]
    return root.get("targetNamespace"), [ns for ns in imports if ns]


def version_of(path: Path, model_dir: Path) -> str | None:
    """Nearest ancestor directory below model_dir matching a version
    pattern (e.g. "3.0" in citygml/building/3.0/building.xsd)."""
    for part in reversed(path.relative_to(model_dir).parts[:-1]):
        if VERSION_RE.fullmatch(part):
            return part
    return None


def topo_order(paths: list[Path], infos: dict) -> list[Path]:
    """Dependencies first: a schema is processed after the same-group
    schemas its <import> declarations resolve to."""
    ns_to_path = {}
    for p in paths:
        ns_to_path.setdefault(infos[p][0], p)
    deps = {p: {ns_to_path[ns] for ns in infos[p][1]
                if ns in ns_to_path and ns_to_path[ns] != p}
            for p in paths}
    order, remaining = [], dict(sorted((p, d) for p, d in deps.items()))
    while remaining:
        ready = [p for p, d in remaining.items() if not d & remaining.keys()]
        if not ready:  # import cycle: fall back to alphabetical
            ready = [next(iter(remaining))]
        order.extend(ready)
        for p in ready:
            del remaining[p]
    return order


def pick_core(paths: list[Path], model_dir_name: str, core_arg: str | None) -> Path:
    """The core/base schema of one version group. There is always one:
    designated by the user (--core or interactive pick) when the folder
    holds no core/base-named schema."""
    if core_arg:
        matches = [p for p in paths
                   if p.stem.lower() == core_arg.lower()
                   or p.name.lower() == core_arg.lower()]
        if matches:
            return matches[0]
        print(f"note: --core {core_arg!r} matches no schema in this version; "
              f"falling back to normal core detection")

    if len(paths) == 1:
        return paths[0]
    named = [p for p in paths
             if p.stem.lower() in ("core", "base", f"{model_dir_name.lower()}core",
                                   f"{model_dir_name.lower()}base")]
    if named:
        return sorted(named)[0]
    print("No core.xsd/base.xsd found; pick the core schema "
          "(or rerun with --core <name>):")
    for i, p in enumerate(paths, 1):
        print(f"  {i}) {p.name}")
    try:
        choice = input("core schema number: ").strip()
    except EOFError:
        sys.exit("no core schema given; rerun with --core <name>")
    if not choice.isdigit() or not 1 <= int(choice) <= len(paths):
        sys.exit(f"invalid choice: {choice!r}")
    return paths[int(choice) - 1]


def package_filename(path: Path, paths: list[Path]) -> str:
    """<stem>.puml, prefixed with the parent directory when several
    schemas of the version group share the same stem."""
    stem = path.stem.lower()
    if sum(1 for p in paths if p.stem.lower() == stem) > 1:
        stem = f"{path.parent.name}_{stem}"
    return f"{stem}.puml"


def run_step(module_name: str, args: list) -> None:
    """Run one step's main() in-process with a patched sys.argv."""
    module = importlib.import_module(module_name)
    old_argv = sys.argv
    sys.argv = [module_name, *(str(a) for a in args)]
    try:
        module.main()
    finally:
        sys.argv = old_argv


def version_sort_key(version: str | None) -> list:
    return [int(p) if p.isdigit() else p
            for p in re.split(r"(\d+)", version or "")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build all PlantUML class diagrams for a data-model "
                    "schema folder (all versions found in it).")
    parser.add_argument("model_folder", type=Path,
                        help="data-model schema folder (e.g. "
                             "schemas/xsds/citygml); may contain multiple "
                             "versions of the same data model")
    parser.add_argument("--core",
                        help="file or stem name of the core/base schema")
    args = parser.parse_args()

    model_dir = args.model_folder
    if not model_dir.is_dir():
        sys.exit(f"not a directory: {model_dir}")
    model = NAME_MAP.get(model_dir.name.lower(), model_dir.name.capitalize())

    # Import resolution is scoped to the given folder: external namespaces
    # are only considered when deliberately stored in the same folder.
    import step02_inheritance
    step02_inheritance.SEARCH_ROOT = model_dir

    xsds = sorted(model_dir.rglob("*.xsd"))
    if not xsds:
        sys.exit(f"no .xsd files found under {model_dir}")
    groups: dict[str | None, list[Path]] = {}
    for xsd in xsds:
        groups.setdefault(version_of(xsd, model_dir), []).append(xsd)
    infos = {xsd: schema_info(xsd) for xsd in xsds}

    found = ", ".join(str(v) for v in sorted(groups, key=version_sort_key))
    print(f"Data model: {model} ({len(xsds)} schemas, versions: {found})")

    for version in sorted(groups, key=version_sort_key):
        paths = groups[version]
        order = topo_order(paths, infos)
        core = pick_core(paths, model_dir.name, args.core)
        center = schema_prefix(core) or core.stem.lower()

        parts = [Path("output"), model]
        if version:
            parts.append(version)
        out_dir = Path(*parts) / "UMLClassDiagram"

        print(f"\n=== {model} {version or '(no version)'} "
              f"-> {out_dir} ({len(paths)} packages, core: {core.name}) ===")
        for xsd in order:
            out_path = out_dir / package_filename(xsd, paths)
            print(f"-- {xsd.name} -> {out_path.name}")
            for step in STEP_MODULES:
                run_step(step, [xsd, out_path])
        run_step("step09_all_packages",
                 [out_dir, out_dir / "all_packages.puml", center])


if __name__ == "__main__":
    main()
