"""Step 11: crow's-foot E-R diagram centered on one class of a module.

The user picks a module .puml (a previously generated class diagram)
and one of its classes; the script draws a crow's-foot E-R diagram
(PlantUML `entity` syntax) with that class at the center:

- the center class becomes an entity box carrying its attributes
  (mandatory ones — XSD minOccurs >= 1 — marked with `*`; `~` adeOf
  members are skipped per convention);
- every relation edge touching the center (both directions) becomes a
  crow's-foot relationship to a neighbor entity; attributes whose value
  type is a real class of the same module are promoted to
  relationships the same way (as in step 10's promote_attribute_relations);
- the center's direct inheritance parent(s) are added as entities with
  a generalization arrow (EER ISA);
- neighbor/parent entities are drawn as empty boxes to keep the star
  focused on the center.

Note on notation: the original request was a "Chen diagram", but
classic Chen shapes (oval attributes, diamond relationships) are NOT
expressible in PlantUML — its ER syntax is crow's-foot (verified
against the Jetty 12 server 2026-10-24: `usecase` ovals cannot mix with
class/entity diagrams, the `<< (D,...) >>` spot is a lettered circle
not a diamond, and `@startdot` passthrough is suppressed by the
server). By user decision (2026-10-24) the diagrams use crow's-foot
notation and everything is NAMED "crowsfoot" (files, directories, nav
labels) rather than "chen", to avoid implying Chen notation.

Cardinality mapping (XSD min..max -> crow's foot, target end):
"1" -> `||`, "0..1" -> `o|`, "0..*"/"*" -> `o{`, "1..*" -> `|{`.
Source ends are `||` only for composition (XSD-guaranteed "1"); other
source ends stay plain (unknown from the XSD).

Usage:
    python3 step11_crowsfoot.py <module.puml> <class> [output.puml]

<class> accepts the display name (`core:CityModel`), the bare local name
(`CityModel`) or the alias (`core_CityModel`). Default output:
<module_dir>/crowsfoot/<module_stem>-<classname>.puml (all lowercase).
Not invoked by every_class.py — run manually, like step 10.
"""

import re
import sys
from pathlib import Path

from step01_list_classes import alias_of, generation_footer
from step09_all_packages import ATTR_RE, DECL_RE, STEREO_RE, decl_key

INHERIT_RE = re.compile(r'^"(\w+)" <\|-- "(\w+)"')
RELATION_RE = re.compile(
    r'^"(\w+)"(?: "([^"]+)")? (o--|\*--|\.\.>) "([^"]+)" "(\w+)" : (.+)$')

# XSD cardinality -> crow's-foot symbol at the target (right) end
CROWS_FOOT = {"1": "||", "0..1": "o|", "0..*": "o{", "*": "o{",
              "1..*": "|{"}


def parse_diagram(path: Path) -> dict:
    """Parse a module .puml into classes (with attributes) and edges.

    Classes: alias -> {name, abstract, stereo, real, attrs}, where real
    classes are the ones declared inside the `package` block (stubs stay
    outside, per the project convention) and attrs are (visible, name,
    type, card) with `visible` False for `~` (adeOf) members. Edges:
    (kind, src_alias, dst_alias, src_card, dst_card, label) with kind in
    {"inherit", "compose", "aggregate", "depend"}."""
    classes, edges, title_first = {}, [], None
    in_title = depth = 0
    body_alias, body_depth = None, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "title":
            in_title = True
            continue
        if line == "end title":
            in_title = False
            continue
        if in_title:
            m = re.match(r"^  (.+)$", line)
            if m and title_first is None:
                title_first = m.group(1)
            continue

        if body_alias and depth == body_depth:
            a = ATTR_RE.match(line)
            if a:
                vis, name, prefix, typ, card = a.groups()
                classes[body_alias]["attrs"].append(
                    (vis != "~", name, f"{prefix}:{typ}", card))

        m = DECL_RE.match(line)
        new_depth = depth + line.count("{") - line.count("}")
        if m:
            alias = decl_key(m)
            s = STEREO_RE.search(line)
            if alias not in classes:
                classes[alias] = {
                    "name": m.group(2), "abstract": m.group(1).startswith("abstract"),
                    "stereo": s.group(1) if s else "", "real": depth == 1,
                    "attrs": []}
            if new_depth > depth:  # opening a body
                body_alias = alias
                body_depth = new_depth
        else:
            for regex, kind in ((INHERIT_RE, "inherit"),):
                m2 = regex.match(line)
                if m2:
                    edges.append((kind, m2.group(1), m2.group(2),
                                  None, None, ""))
            m3 = RELATION_RE.match(line)
            if m3:
                src, src_card, arrow, dst_card, dst, label = m3.groups()
                kind = {"o--": "aggregate", "*--": "compose",
                        "..>": "depend"}[arrow]
                edges.append((kind, src, dst, src_card, dst_card, label))
        depth = new_depth
        if depth < body_depth:
            body_alias = None
    return {"classes": classes, "edges": edges, "title": title_first}


def find_center(classes: dict, query: str) -> str:
    """Resolve the user's class query to an alias. Accepts the prefixed
    display name, the bare local name or the alias; refuses ambiguous or
    stub-only matches."""
    for alias, c in classes.items():
        if query in (alias, c["name"]):
            if c["real"]:
                return alias
            break
    matches = [a for a, c in classes.items()
               if c["real"] and c["name"].split(":")[-1] == query]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        real = sorted(c["name"] for c in classes.values() if c["real"])
        sys.exit(f"class '{query}' not found among the real classes of "
                 f"this module. Available:\n  " + "\n  ".join(real))
    sys.exit(f"class name '{query}' is ambiguous: "
             + ", ".join(classes[a]["name"] for a in matches))


def build_crowsfoot(diagram: dict, center: str) -> str:
    """Assemble the crow's-foot E-R diagram source around `center`."""
    classes, edges = diagram["classes"], diagram["edges"]
    c = classes[center]

    # Relationships touching the center (both directions), plus
    # attribute promotion: an attribute whose value type is a real class
    # of this module becomes a relationship to that entity.
    relations = []
    for kind, src, dst, src_card, dst_card, label in edges:
        if kind != "inherit" and center in (src, dst):
            relations.append((src, dst, src_card, dst_card, label))
    kept_attrs = []
    for visible, name, typ, card in c["attrs"]:
        target = alias_of(typ)
        if visible and target in classes and classes[target]["real"] \
                and target != center:
            relations.append((center, target, None, card or "1", name))
        else:
            kept_attrs.append((visible, name, typ, card))

    neighbors = {a for r in relations for a in r[:2]} - {center}
    parents = [src for kind, src, dst, *_ in edges
               if kind == "inherit" and dst == center]
    entities = neighbors | set(parents)

    lines = ["@startuml",
             "' Generated by step11_crowsfoot.py - do not edit.",
             "' E-R diagram (crow's foot) centered on one class;",
             "' classic Chen shapes are not expressible in PlantUML.",
             ""]
    stereo = f" <<{c['stereo']}>>" if c["stereo"] else ""
    shown_attrs = [(v, n, t, cd) for v, n, t, cd in kept_attrs if v]
    if shown_attrs:
        lines.append(f'entity "{c["name"]}" as {center}{stereo} {{')
        for _, name, typ, card in shown_attrs:
            mandatory = "*" if card and card.split("..")[0] != "0" \
                and card != "0" else ""
            lines.append(f"  {mandatory} {name} : {typ}")
        lines.append("}")
    else:
        lines.append(f'entity "{c["name"]}" as {center}{stereo}')
    for alias in sorted(entities):
        n = classes.get(alias)
        name = n["name"] if n else alias
        s = f' <<{n["stereo"]}>>' if n and n["stereo"] else ""
        lines.append(f'entity "{name}" as {alias}{s}')

    lines.append("")
    for src in parents:
        lines.append(f'"{src}" <|-- "{center}"')
    seen = set()
    for src, dst, src_card, dst_card, label in relations:
        if (src, dst, label) in seen:
            continue
        seen.add((src, dst, label))
        left = '||' if src_card == "1" else ''
        right = CROWS_FOOT.get(dst_card or "", "")
        lines.append(f'"{src}" {left}--{right} "{dst}" : {label}')

    base = " - ".join((diagram["title"] or "").split(" - ")[:2])
    lines += ["", "title",
              f"  {base} - {c['name']} - Crow's Foot E-R Diagram",
              "end title", "", generation_footer(), "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__.split("Usage:")[1].strip())
    module = Path(sys.argv[1])
    diagram = parse_diagram(module)
    center = find_center(diagram["classes"], sys.argv[2])
    class_part = diagram["classes"][center]["name"].split(":")[-1].lower()
    out_path = (Path(sys.argv[3]) if len(sys.argv) > 3 else
                module.parent / "crowsfoot" / f"{module.stem}-{class_part}.puml")

    source = build_crowsfoot(diagram, center)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    n_rel = sum(1 for l in source.splitlines() if "--" in l and '" :' in l)
    print(f"Crow's-foot E-R diagram for {diagram['classes'][center]['name']} "
          f"({n_rel} relationships), written to {out_path}")


if __name__ == "__main__":
    main()
