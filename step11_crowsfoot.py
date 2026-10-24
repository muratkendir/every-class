"""Step 11: crow's-foot E-R diagram centered on one class of a module.

The user picks a module .puml (a previously generated class diagram)
and one of its classes; the script draws a crow's-foot E-R diagram
(PlantUML `entity` syntax) with that class at the center, including the
members INHERITED from its ancestor chain (user decision 2026-10-24):

- the center class becomes an entity box carrying its attributes
  (mandatory ones — XSD minOccurs >= 1 — marked with `*`; `~` adeOf
  members are skipped per convention);
- relations are typed by the OTHER end's stereotype: a «FeatureType»
  target becomes a crow's-foot relationship; a known non-FeatureType
  target (DataType, ObjectType, Enumeration, ...) is shown as an
  attribute row (`name : Type [card]`) instead; targets with unknown
  stereotype (external stubs) stay relationships. Same-module
  class-typed attributes follow the same rule (promoted only when the
  target is a «FeatureType», as in step 10's attribute promotion);
- inherited attributes and relationships (from the whole ancestor
  chain, closest ancestor first) are shown in GRAY
  (`<color:gray>...</color>` in the box, `-[#gray]-` edges) so they
  cannot be confused with the class's own members; a member present
  both as own and inherited is drawn once, as own;
- the full ancestor chain is drawn as empty entities connected by
  generalization arrows (EER ISA), documenting where the gray members
  come from; neighbor entities are empty boxes to keep the star focused
  on the center.

Cross-module resolution: ancestors and relation targets usually live in
OTHER modules (e.g. bldg classes inherit from core:), where the module
file only carries stubs. If `<module_dir>/all_packages.puml` exists it
is parsed as an index of all real classes of the model-version
(attributes, relations, stereotypes) — the module file stays
authoritative, the index only fills gaps. The chain stops at ancestors
not found in the index (external stubs like gml: classes are not
flattened: their base attributes would flood every FeatureType box).

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

GRAY = "gray"


def parse_diagram(path: Path) -> dict:
    """Parse a module .puml into classes (with attributes) and edges.

    Classes: alias -> {name, abstract, stereo, real, attrs}, where real
    classes are the ones declared inside a `package` block (stubs stay
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
                    "stereo": s.group(1) if s else "", "real": depth >= 1,
                    "attrs": []}
            if new_depth > depth:  # opening a body
                body_alias = alias
                body_depth = new_depth
        else:
            m2 = INHERIT_RE.match(line)
            if m2:
                edges.append(("inherit", m2.group(1), m2.group(2),
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


def load_index(module: Path) -> dict:
    """The module diagram, completed with all_packages.puml (same
    directory) when present: it carries the real classes of every module
    of the model-version, so ancestors and relation targets from other
    modules resolve with their attributes and stereotypes. The module
    file stays authoritative; the index only fills gaps."""
    diagram = parse_diagram(module)
    combined = module.parent / "all_packages.puml"
    if combined.exists() and combined != module:
        extra = parse_diagram(combined)
        for alias, c in extra["classes"].items():
            if alias not in diagram["classes"] \
                    or (not diagram["classes"][alias]["real"] and c["real"]):
                diagram["classes"].setdefault(alias, c)
        known = {(k, s, d, l) for k, s, d, _, _, l in diagram["edges"]}
        for e in extra["edges"]:
            if (e[0], e[1], e[2], e[5]) not in known:
                diagram["edges"].append(e)
                known.add((e[0], e[1], e[2], e[5]))
    return diagram


def find_center(classes: dict, query: str, module_classes: dict) -> str:
    """Resolve the user's class query to an alias. The class must be a
    real class of the given module (not just of the index); accepts the
    prefixed display name, the bare local name or the alias and refuses
    ambiguous or stub-only matches."""
    for alias, c in module_classes.items():
        if query in (alias, c["name"]):
            if c["real"]:
                return alias
            break
    matches = [a for a, c in module_classes.items()
               if c["real"] and c["name"].split(":")[-1] == query]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        real = sorted(c["name"] for c in module_classes.values() if c["real"])
        sys.exit(f"class '{query}' not found among the real classes of "
                 f"this module. Available:\n  " + "\n  ".join(real))
    sys.exit(f"class name '{query}' is ambiguous: "
             + ", ".join(module_classes[a]["name"] for a in matches))


def ancestor_chain(classes: dict, edges: list, center: str) -> list:
    """The transitive inheritance ancestors of `center`, closest first.
    Stops at ancestors not present as real classes in the index
    (external stubs are not flattened)."""
    chain, seen, frontier = [], {center}, [center]
    while frontier:
        nxt = []
        for child in frontier:
            for kind, src, dst, *_ in edges:
                if kind == "inherit" and dst == child and src not in seen:
                    if classes.get(src, {}).get("real"):
                        chain.append(src)
                    seen.add(src)
                    nxt.append(src)
        frontier = nxt
    return chain


def members_of(classes: dict, edges: list, x: str,
               incoming: bool = True) -> tuple:
    """(attribute rows, relations) of class x.

    Attribute rows: (name, type, card) — the visible `~`-less
    attributes. Relations: (src, dst, src_card, dst_card, label) —
    promotable attributes (value type is a real class in the index)
    plus relation edges touching x. With `incoming` False only edges
    SOURCED at x count: incoming edges to an ancestor are other
    classes' relations, not members the subclass inherits (and they
    would flood the diagram with the whole model's references to the
    base classes)."""
    attrs = []
    rels = []
    promoted = set()
    for visible, name, typ, card in classes[x]["attrs"]:
        target = alias_of(typ)
        if visible and target != x and classes.get(target, {}).get("real"):
            rels.append((x, target, None, card or "1", name))
            promoted.add((name, typ))
    for visible, name, typ, card in classes[x]["attrs"]:
        if visible and (name, typ) not in promoted:
            attrs.append((name, typ, card))
    for kind, src, dst, src_card, dst_card, label in edges:
        if kind != "inherit" and (src == x or (incoming and dst == x)):
            rels.append((src, dst, src_card, dst_card, label))
    return attrs, rels


def split_relations(classes: dict, x: str, rels: list) -> tuple:
    """Split relations touching x into (crow's-foot edges, attribute
    rows) by the OTHER end's stereotype: «FeatureType» -> edge; known
    non-FeatureType -> attribute row (only when x is the source);
    unknown stereotype (external stub) -> edge."""
    edges_out, attr_rows = [], []
    for src, dst, src_card, dst_card, label in rels:
        other = dst if src == x else src
        stereo = classes.get(other, {}).get("stereo", "")
        if stereo and stereo != "FeatureType" and src == x:
            name = classes[other]["name"]
            attr_rows.append((label, name, dst_card))
        else:
            edges_out.append((src, dst, src_card, dst_card, label))
    return edges_out, attr_rows


def build_crowsfoot(diagram: dict, module_classes: dict,
                    center: str) -> str:
    """Assemble the crow's-foot E-R diagram source around `center`,
    flattening inherited members in gray."""
    classes, edges = diagram["classes"], diagram["edges"]
    c = classes[center]
    chain = ancestor_chain(classes, edges, center)

    def render_members(x: str, gray: bool, own_keys: set):
        """Attribute rows and relationship edges of x (in build order).
        Inherited (gray) relations are FLATTENED onto the center — the
        ancestor's end of the edge is replaced by the center — and those
        duplicating an own relation are skipped."""
        attrs, rels = members_of(classes, edges, x, incoming=not gray)
        rel_edges, rel_attrs = split_relations(classes, x, rels)
        rows, lines = [], []
        for name, typ, card in attrs:
            rows.append((name, typ, card))
        rows += rel_attrs
        for src, dst, src_card, dst_card, label in rel_edges:
            if gray:
                if src == x:
                    src = center
                if dst == x:
                    dst = center
            other = dst if src == center else src
            if gray and (src == center, other, label) in own_keys:
                continue
            lines.append((src, dst, src_card, dst_card, label))
        return rows, lines

    own_attrs, own_rels = members_of(classes, edges, center)
    own_edges, own_attr_rows = split_relations(classes, center, own_rels)
    own_keys = {(s == center, d if s == center else s, l)
                for s, d, _, _, l in own_edges}

    box_rows = []  # (text, gray); deduplicated by (name, type) — the
    # first occurrence wins (own beats inherited, and an attribute
    # promoted to a relation-derived row is not repeated)
    seen_rows = set()

    def add_row(name: str, typ: str, card: str, gray: bool,
                show_card: bool) -> None:
        if (name, typ) in seen_rows:
            return
        seen_rows.add((name, typ))
        mandatory = "*" if not show_card and card \
            and card.split("..")[0] != "0" and card != "0" else ""
        text = f"{mandatory} {name} : {typ}".lstrip() \
            + (f" [{card}]" if show_card and card else "")
        box_rows.append((text, gray))

    for name, typ, card in own_attrs:
        add_row(name, typ, card, False, False)
    for name, typ, card in own_attr_rows:
        add_row(name, typ, card, False, True)
    edge_lines = [(s, d, sc, dc, l, False)
                  for s, d, sc, dc, l in own_edges]
    for anc in chain:
        rows, lines = render_members(anc, True, own_keys)
        for name, typ, card in rows:
            add_row(name, typ, card, True, True)
        edge_lines += [(s, d, sc, dc, l, True) for s, d, sc, dc, l in lines]

    # Entities: ancestors (ISA chain) + every other end of an edge.
    other_ends = {a for s, d, *_rest, _g in edge_lines for a in (s, d)}
    entities = (other_ends | set(chain)) - {center}

    lines = ["@startuml",
             "' Generated by step11_crowsfoot.py - do not edit.",
             "' E-R diagram (crow's foot) centered on one class;",
             "' inherited members are shown in gray; classic Chen",
             "' shapes are not expressible in PlantUML.",
             ""]
    stereo = f" <<{c['stereo']}>>" if c["stereo"] else ""
    if box_rows:
        lines.append(f'entity "{c["name"]}" as {center}{stereo} {{')
        for text, gray in box_rows:
            lines.append(f"  <color:{GRAY}>{text}</color>" if gray
                         else f"  {text}")
        lines.append("}")
    else:
        lines.append(f'entity "{c["name"]}" as {center}{stereo}')
    for alias in sorted(entities):
        n = classes.get(alias)
        name = n["name"] if n else alias
        s = f' <<{n["stereo"]}>>' if n and n["stereo"] else ""
        lines.append(f'entity "{name}" as {alias}{s}')

    lines.append("")
    for child, parent in zip([center] + chain, chain):
        lines.append(f'"{parent}" <|-- "{child}"')
    seen = set()
    for src, dst, src_card, dst_card, label, gray in edge_lines:
        if (src, dst, label) in seen:
            continue
        seen.add((src, dst, label))
        left = "||" if src_card == "1" else ""
        right = CROWS_FOOT.get(dst_card or "", "")
        arrow = f"{left}-[#{GRAY}]-{right}" if gray else f"{left}--{right}"
        lbl = f"<color:{GRAY}>{label}</color>" if gray else label
        lines.append(f'"{src}" {arrow} "{dst}" : {lbl}')

    base = " - ".join((diagram["title"] or "").split(" - ")[:2])
    lines += ["", "title",
              f"  {base} - {c['name']} - Crow's Foot E-R Diagram",
              "end title", "", generation_footer(), "@enduml", ""]
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__.split("Usage:")[1].strip())
    module = Path(sys.argv[1])
    module_classes = parse_diagram(module)["classes"]
    diagram = load_index(module)
    center = find_center(diagram["classes"], sys.argv[2], module_classes)
    class_part = diagram["classes"][center]["name"].split(":")[-1].lower()
    out_path = (Path(sys.argv[3]) if len(sys.argv) > 3 else
                module.parent / "crowsfoot" / f"{module.stem}-{class_part}.puml")

    source = build_crowsfoot(diagram, module_classes, center)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    n_rel = sum(1 for l in source.splitlines() if "--" in l and '" :' in l
                or re.search(r'-\[gray\]-', l))
    n_gray = source.count(f"<color:{GRAY}>")
    print(f"Crow's-foot E-R diagram for {diagram['classes'][center]['name']} "
          f"({n_rel} relationships, {n_gray} gray inherited element(s)), "
          f"written to {out_path}")


if __name__ == "__main__":
    main()
