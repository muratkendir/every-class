"""Step 10: user-selected compilation of module diagrams into one file.

Same merge as step 09 (build_combined from step09_all_packages: each
class declared exactly once, owner-first inlining of the module
sources, connectivity-based hidden layering) but restricted to the
modules named on the command line — a combined diagram of a SUBSET of
the packages instead of all of them.

Usage:
    python3 step10_compilation.py [scan_dir] <output_path> <module> [<module> ...]

    scan_dir     directory holding the module .puml files
                 (default: step 09's DEFAULT_DIR)
    output_path  where to write the combined .puml
    module       module file stem(s), e.g. core con bldg xal
                 (order on the command line does not matter; the
                 modules are inlined owner-first, as in step 09)

Example:
    python3 step10_compilation.py docs/output/CityGML/3.0/UMLClassDiagram \
        compilations/core-con-bldg-xal.puml core con bldg xal

The hidden-link layering is centered on the "core" package when it is
among the selected modules, otherwise on the first selected package.
The title is "<model> - <version> - <Module, List & Names> Modules",
derived from the module files like step 09 derives its own.
"""

import sys
from pathlib import Path

from step09_all_packages import (DEFAULT_DIR, build_combined, include_order,
                                 parse_module, strip_frame)


def resolve_modules(scan_dir: Path, args: list[str]) -> dict[str, Path]:
    """Map each module argument to its .puml file in scan_dir, by file
    stem or by package name ("con" -> construction.puml)."""
    available = {p.stem: p for p in sorted(scan_dir.glob("*.puml"))}
    by_package = {}
    for stem, path in available.items():
        pkg = parse_module(path)["package"]
        if pkg and pkg not in by_package:
            by_package[pkg] = path
    paths = {}
    for arg in args:
        key = arg[:-5] if arg.endswith(".puml") else arg
        path = available.get(key) or available.get(key.lower()) \
            or by_package.get(key) or by_package.get(key.lower())
        if path is None:
            sys.exit(f"unknown module {arg!r} in {scan_dir}; "
                     f"available: {', '.join(available)}")
        paths[path.name] = path
    return paths


def main() -> None:
    args = sys.argv[1:]
    scan_dir = Path(args.pop(0)) if args and Path(args[0]).is_dir() else DEFAULT_DIR
    if len(args) < 2:
        sys.exit(__doc__)
    out_path = Path(args.pop(0))
    module_args = args

    paths = resolve_modules(scan_dir, module_args)
    modules = {name: parse_module(p) for name, p in paths.items()}
    texts = {name: strip_frame(p.read_text(encoding="utf-8").splitlines())
             for name, p in paths.items()}
    order = include_order(modules)

    # Diagram title: "<model> - <version>" from any module's title
    # ("CityGML - 3.0 - Core - Only XSD based" -> "CityGML - 3.0"),
    # plus the selected packages in owner-first order.
    first_title = next((m["title"] for m in modules.values() if m["title"]), "")
    base = " - ".join(first_title.split(" - ")[:2])
    pkgs = []
    for name in order:
        pkg = modules[name]["package"] or Path(name).stem
        if pkg not in pkgs:
            pkgs.append(pkg)
    display = [p.capitalize() if p.islower() else p for p in pkgs]
    label = display[0] if len(display) == 1 else \
        ", ".join(display[:-1]) + " & " + display[-1]
    title = f"{base} - {label} Modules"

    center = "core" if "core" in pkgs else pkgs[0]

    source = build_combined(modules, texts, order, title, center,
                            header="step10_compilation.py")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(f"{len(order)} modules merged ({', '.join(pkgs)}), "
          f"written to {out_path}")


if __name__ == "__main__":
    main()
