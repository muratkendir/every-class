# every-class

Reads XSD schemas from `schemas/` and converts them into UML class diagrams
via PlantUML text output. Developed incrementally: each step is a separate
Python file dedicated to one purpose; `every_class.py` is the main
application that detects model/versions/core schema in a folder and runs
all steps (see its section below). Use `python3` (plain `python` does not
exist on this machine). Standard library only (`xml.etree.ElementTree`).

## Scope

- Schema root is `schemas/xsds/` (restructured from the original flat
  `schemas/<model>/` layout): `schemas/xsds/<model>/...` with models
  citygml, gml, indoorgml, infragml (part0-7), kml, pipelineml, xlink,
  filter, georss. All step defaults (`DEFAULT_XSD`) point at
  `schemas/xsds/citygml/3.0/core.xsd`.
- Start with CityGML 3.0: `core.xsd` (present at
  `schemas/xsds/citygml/3.0/core.xsd`), then Construction, Building,
  CityFurniture, CityObjectGroup and Appearance XSDs (all present under
  `schemas/xsds/citygml/<module>/3.0/`).
- External namespaces (GML, XLink, ...) are NOT resolved/downloaded; their
  types are kept as prefixed names and drawn as plain stub classes under
  an "' External types" comment, OUTSIDE the package block (no
  `<<external>>` stereotype — removed by user decision; the out-of-package
  position is what marks them as external).
  A stub whose local name starts with `Abstract` is emitted as
  `abstract class` (name heuristic, since external XSDs are unavailable);
  the same `abstract="true"` XSD attribute drives local classes.

## Conventions established

- Every class name is prefixed with the schema's own namespace prefix
  (e.g. `core:AddressType`) and quoted in PlantUML, so multiple `.puml`
  files can be merged without name clashes. All local classes, simple
  types, and union groups are wrapped in a `package <prefix> { ... }`
  block (e.g. `package core`); external stubs stay outside the package.
- Diagram title is derived from the schema path
  (`CityGML - 3.0 - Core - Only XSD based`) with the target namespace URI
  as a sub-header (`title ... end title` block).
- Output location is derived from the schema path the same way
  (`model_version` + `default_output` in step 01):
  `output/<DataModelName>/<Version>/UMLClassDiagram/<module>.puml`, where
  `<DataModelName>` comes from `NAME_MAP` (e.g. citygml → CityGML),
  `<Version>` is the numeric ancestor directory, and `<module>` is the
  XSD file stem lowercased (cityFurniture.xsd → cityfurniture.puml).
  All steps default to this when no output path is passed, so other data
  models/versions land in their own sibling directories.
- XSD mapping decisions so far:
  - top-level named `<complexType>` → UML class (`abstract="true"` → `abstract class`)
  - trailing `"Type"` suffix is stripped from all displayed names (e.g.
    `AddressType` → `core:Address`, `gml:AbstractFeatureType` → stub
    `gml:AbstractFeature`); the original XSD name is kept in the
    `xsd_name` backup attribute of each parsed class
  - in attribute value types, a trailing `"Property"` suffix is also
    stripped (`core:ADEOfAddressProperty` → `core:ADEOfAddress`,
    `gml:MultiPointProperty` → `gml:MultiPoint`); class declarations keep
    their `...Property` names and `$property` tags unchanged
  - `<extension base>`/`<restriction base>` in `complexContent` → generalization (`Parent <|-- Child`)
  - direct `<element>` children of a complexType → UML attributes, shown as
    `name : type`; types keep their namespace prefix (`gml:Code`,
    `xAL:Address`); unprefixed XSD built-ins are shown as `xs:<name>`;
    anonymous inline types resolve to the reference they wrap
    (elements nested inside another element are not attributes)
- `...PropertyType` types are encoding artifacts (associations), not real
  UML classes — handling them is a planned later step.
- Classes whose name starts with `ADEOf` (ADE hooks) are kept in the
  `.puml` file tagged with `$adeOf` and removed from rendering via a single
  `remove $adeOf` line; delete that line to show them.
- Classes whose name ends with `Property` (property pseudo-classes) are
  likewise tagged `$property` and removed via `remove $property`. A class
  matching both rules carries both tags (`$property $adeOf`). Tags are used
  instead of stereotypes; verified working on PlantUML 1.2020.02.
- Attributes starting with `adeOf` are kept in the file as package members
  (`~ name : type`) and hidden via a single `hide package members` line.
  Note: verified NOT to work on PlantUML 1.2020.02 (local); expected to
  work on newer versions.
- Attributes whose value type is in another namespace (type prefix differs
  from the schema's own prefix, e.g. `gml:`, `xAL:`, `xs:`) are marked as
  protected members (`# name : type`) and SHOWN by default; the file
  contains a commented-out `' hide protected members` line that can be
  uncommented to hide them.
  The `~` marker takes precedence over `#` if both would apply.

## Schemas processed

- `schemas/xsds/citygml/3.0/core.xsd` → `output/CityGML/3.0/UMLClassDiagram/core.puml` (run steps 01–08
  with no arguments)
- `schemas/xsds/citygml/construction/3.0/construction.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/construction.puml` (pass both paths as arguments to each
  step). Stereotypes work across modules: step 06's `build_graph` resolves
  `<import>` declarations against local XSD files (by target namespace,
  recursive) and extends the inheritance graph, so `con:` classes inherit
  «FeatureType» from `core:` bases. Relations to core targets still stay
  attributes (target classes are not merged into the diagram).
- `schemas/xsds/citygml/building/3.0/building.xsd` → `output/CityGML/3.0/UMLClassDiagram/building.puml`
  (42 classes, 10 inheritance relations, 77 attributes, 15 class relations —
  1 composition, 14 aggregation —, 10 «FeatureType»; imports construction and
  core, both resolved by `build_graph`).
- `schemas/xsds/citygml/cityfurniture/3.0/cityFurniture.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/cityfurniture.puml` (4 classes, 1 inheritance relation,
  6 attributes, 0 class relations, 1 «FeatureType»; local XSD is trimmed —
  61 lines, only `class`/`function`/`usage` attributes on `CityFurnitureType`).
- `schemas/xsds/citygml/cityobjectgroup/3.0/cityObjectGroup.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/cityobjectgroup.puml` (6 classes, 2 inheritance relations,
  9 attributes, 3 class relations — composition `CityObjectGroup *-- Role :
  groupMember`, aggregation `Role o-- core:AbstractCityObject : groupMember`,
  dependency `CityObjectGroup ..> core:AbstractCityObject : parent` —,
  1 «FeatureType» + 1 «ObjectType»). The two `core:AbstractCityObject`
  relations target an external stub drawn via the appinfo rules below.
- `schemas/xsds/citygml/appearance/3.0/appearance.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/appearance.puml` (32 classes, 9 inheritance relations,
  48 attributes, 3 class relations — 2 composition, 1 aggregation —,
  6 «FeatureType» + 1 «ObjectType» + 3 «DataType», 2 «Enumeration»
  (`TextureType`, `WrapMode`) + 2 «BasicType» (`Color`, `ColorPlusOpacity`);
  no union groups; imports core, resolved by `build_graph` —
  `core:AbstractAppearance` and `core:AbstractFeature` appear as external
  inheritance bases).
- `schemas/xsds/citygml/dynamizer/3.0/dynamizer.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/dynamizer.puml` (34 classes, 7 inheritance relations,
  79 attributes, 6 class relations — 3 composition, 2 aggregation,
  1 dependency —, 7 «FeatureType» + 3 «DataType», 1 «Enumeration»
  (`TimeseriesTypeValue`); no union groups; imports core, resolved by
  `build_graph` — `core:AbstractDynamizer` is drawn as an external stub
  like all cross-module bases (it IS defined in core.xsd; stubs just
  mean "not declared in this module's own XSD").
- `schemas/xsds/citygml/generics/3.0/generics.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/generics.puml` (32 classes, 12 inheritance relations,
  49 attributes, 0 class relations, 4 «FeatureType» (the four Generic
  spaces) + 8 «DataType»; no union groups, no enums). All 12 inheritance
  bases are core: classes drawn as external stubs (per-module convention:
  imported classes are not merged into the diagram); `genericAttribute :
  core:AbstractGenericAttribute [1..*]` stays an attribute because its
  target lives in another namespace.
- `schemas/xsds/citygml/landuse/3.0/landUse.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/landuse.puml` (4 classes, 1 inheritance relation,
  6 attributes, 0 class relations, 1 «FeatureType»; local XSD is trimmed —
  61 lines, only `class`/`function`/`usage` attributes on `LandUseType`,
  same shape as the cityfurniture module).
- `schemas/xsds/citygml/pointcloud/3.0/pointCloud.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/pointcloud.puml` (4 classes, 1 inheritance relation,
  7 attributes, 0 class relations, 1 «FeatureType»; local XSD is trimmed —
  66 lines, only the `mimeType`/`pointFile`/`pointFileSrsName`/`points`
  attributes on `PointCloudType`; base `core:AbstractPointCloud` is an
  external stub per the no-merge convention (it IS defined in core.xsd).
- `schemas/xsds/citygml/relief/3.0/relief.xsd` → `output/CityGML/3.0/UMLClassDiagram/relief.puml`
  (24 classes, 6 inheritance relations, 28 attributes, 1 class relation —
  aggregation `ReliefFeature o-- AbstractReliefComponent : reliefComponent`
  `1..*` —, 6 «FeatureType»; no union groups, no enums). Both
  `ReliefFeature` and `AbstractReliefComponent` extend
  `core:AbstractSpaceBoundary` (external stub).
- `schemas/xsds/citygml/transportation/3.0/transportation.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/transportation.puml` (64 classes, 16 inheritance
  relations, 103 attributes, 15 class relations — 13 aggregation,
  2 dependency —, 16 «FeatureType», 2 «Enumeration» (`GranularityValue`,
  `TrafficDirectionValue`); no union groups). External stubs:
  `core:AbstractThematicSurface`, `core:AbstractUnoccupiedSpace`.
- `schemas/xsds/citygml/vegetation/3.0/vegetation.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/vegetation.puml` (12 classes, 3 inheritance relations,
  24 attributes, 0 class relations, 3 «FeatureType» —
  `AbstractVegetationObject` ← `core:AbstractOccupiedSpace` (external
  stub), with `PlantCover` and `SolitaryVegetationObject` below it; no
  enums, no union groups).
- `schemas/xsds/citygml/versioning/3.0/versioning.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/versioning.puml` (10 classes, 2 inheritance relations,
  18 attributes, 6 class relations — 1 composition, 1 aggregation,
  4 dependency —, 2 «FeatureType» (`Version`, `VersionTransition`) +
  1 «DataType» (`Transaction`), 2 «Enumeration» (`TransactionTypeValue`,
  `TransitionTypeValue`); no union groups). The composition
  `VersionTransition *-- Transaction` is demoted to a private member by
  the FeatureType→DataType rule, so only 5 arrows are drawn; the other
  relations target `vers:Version` and the external stubs
  `core:AbstractVersion`, `core:AbstractVersionTransition`,
  `core:AbstractFeatureWithLifespan`.
- `schemas/xsds/citygml/waterbody/3.0/waterBody.xsd` →
  `output/CityGML/3.0/UMLClassDiagram/waterbody.puml` (16 classes, 4 inheritance relations,
  16 attributes, 0 class relations, 4 «FeatureType» — `WaterBody` ←
  `core:AbstractOccupiedSpace`, `AbstractWaterBoundarySurface` ←
  `core:AbstractThematicSurface` (both external stubs), with
  `WaterSurface` and `WaterGroundSurface` below it; no enums, no union
  groups).
- `schemas/xsds/citygml/bridge/3.0/bridge.xsd` → `output/CityGML/3.0/UMLClassDiagram/bridge.puml`
  (28 classes, 7 inheritance relations, 45 attributes, 7 class relations —
  all aggregations, e.g. `AbstractBridge o-- BridgeRoom/BridgeFurniture/
  BridgeInstallation/BridgeConstructiveElement`, `Bridge o-- BridgePart` —,
  7 «FeatureType»; no enums, no union groups). Bases resolve against
  construction and core (imports resolved by `build_graph`); the four
  `con:Abstract…` bases and `core:AbstractUnoccupiedSpace` are drawn as
  external stubs.
- `schemas/xsds/citygml/tunnel/3.0/tunnel.xsd` → `output/CityGML/3.0/UMLClassDiagram/tunnel.puml`
  (28 classes, 7 inheritance relations, 43 attributes, 7 class relations —
  all aggregations, same shape as bridge with `HollowSpace` in the
  `BridgeRoom` role —, 7 «FeatureType»; no enums, no union groups).
  Bases resolve against construction and core; the four `con:Abstract…`
  bases and `core:AbstractUnoccupiedSpace` are external stubs.

### Cross-module relation typing (step 05 + 02)

Step 05's Feature-vs-DataType check (which decides aggregation vs dependency)
uses the cross-module inheritance graph, so relations whose source class
inherits Feature-ness through a `core:`/`con:` base (e.g.
`bldg:AbstractBuilding` ← `con:AbstractConstruction` ← … ←
`gml:AbstractFeature`) are correctly drawn as aggregations, not dependencies.
`build_graph` and `find_schema_by_namespace` live in
`step02_inheritance.py`; step 06 imports them from there and steps 05–08
accept/pass an optional `graph`.

## Steps completed

| Step | File | Purpose | Result |
|---|---|---|---|
| 01 | `step01_list_classes.py` | list classes | 86 classes in core.xsd |
| 02 | `step02_inheritance.py` | generalization relations | 20 relations, 2 external stubs |
| 03 | `step03_attributes.py` | attributes + value types | 123 attributes |
| 04 | `step04_cardinality.py` | attribute cardinalities | `[min..max]` after type, `[1]` omitted |
| 05 | `step05_relations.py` | relations from property wrappers | 18 relations (7 composition, 6 aggregation, 5 dependency) |
| 06 | `step06_stereotypes.py` | UML stereotypes from the XSD | 18 FeatureType, 2 ObjectType, 5 DataType, 3 Enumeration, 5 BasicType |
| 07 | `step07_groups.py` | model groups as «Union» + member relations | CityModelMember union, 5 CityModel member relations |
| 08 | `step08_enumerations.py` | enumeration values as enum members | 3 enums with their values |
| 09 | `step09_all_packages.py` | single combined diagram via `!include` | 17 modules → `output/CityGML/3.0/UMLClassDiagram/all_packages.puml` |

Step 02 imports helpers from step 01 (`parse_classes`, `schema_prefix`,
`qualify`, `strip_type_suffix`, `XSD_NS`); step 03 imports from both;
step 04 imports the parsers from steps 01–03 (`parse_attributes` also
records `min`/`max` occurrence data); step 05 imports from steps 01–04;
step 06 imports from steps 01–05; step 07 imports from steps 01–06.
Step 09 is standalone (no XSD parsing): it scans `output/CityGML/3.0/UMLClassDiagram/*.puml`.

### Combined diagram (step 09)

`step09_all_packages.py` writes `output/CityGML/3.0/UMLClassDiagram/all_packages.puml` (title
"CityGML - 3.0 - All Packages as Single Diagram"), which pulls in every
module file with `!include` lines. Render from inside `output/CityGML/3.0/UMLClassDiagram/` (includes
are basename-relative). Works around three PlantUML 1.2020.02 behaviors
(all verified locally):

- quoted class names are global entities, so duplicate declarations
  across modules merge into one box;
- package membership sticks to the FIRST declaration — modules are
  included owner-first (topological over "stubs a class owned by another
  module"), otherwise a stub seen first strands the class outside its
  package. Stubs are detected STRUCTURALLY: they are the only class
  declarations outside the `package` block (no `<<external>>` marker
  exists anymore);
- a later declaration's stereotype REPLACES the earlier one, but a
  stereotype-less redeclaration never clears it — stubs carry no
  stereotype, so real stereotypes survive the merge and no fixups are
  needed. Included files' own title blocks would clobber the combined
  title, so the title is placed after the includes.

Note: the combined PNG needs `PLANTUML_LIMIT_SIZE=30000` (diagram is
~6900×11300 px, portrait); the SVG renders fine without it.

Orientation: the combined diagram uses `left to right direction`
(portrait — the default top-to-bottom layout spreads ~19000 px wide).
Inheritance flows left→right; core sits at the top (its cluster spans
the left edge) and the modules stack below it. The hidden connectivity
links below are what keep core near the top — without them core lands
mid-diagram (measured: 6th of 17 clusters vertically).

Layout bias (tree-like layering under core): step 09 counts each
module's direct connections to core (lines referencing `core:` in its
.puml: core-typed attributes, external stub declarations,
inheritance/relation edges to core classes) and emits one hidden
package-to-package link per module (`core -[hidden]<dashes>- <pkg>`),
where the dash count (= Graphviz minlen) grows as connectivity
decreases: gen/tran/con (18/13/12 connections) → 2 dashes, the trimmed
2-connection modules (frn, luse, pcl, tun, veg) → 5 dashes. Equal
counts share a layer; distinct counts compress into ~sqrt(n) layers.
Measured on PlantUML 1.2020.02 (SVG cluster positions):

- the layering is a WEAK hint — the real edges dominate ranking, so
  the modules' vertical order follows the connectivity layers only
  loosely (Graphviz crossing-minimization decides);
- class-level hidden links (stronger constraints) crash
  Graphviz/smetana on a diagram this size ("dot/GraphViz has
  crashed"), even with only 16 edges and no minlen;
- a package chain (core → most-connected → … → least-connected)
  renders but produces an ugly diagonal sprawl — tried and rejected;
- directional group pinning (left/right/down around core) was tried
  earlier: chaotic results (core at 18-82% of width depending on group
  composition), abandoned in favor of this scheme;
- putting core at the BOTTOM is impossible: no bottom-to-top
  direction exists and generalization ranks force core upward.

### Model groups (steps 05 + 07)

- `<group ref="...">` usages are expanded as if their members were inline
  (member optional under `<choice>` or group `minOccurs="0"`; unbounded
  group occurrence → unbounded member). This yields CityModel's relations
  `cityObjectMember`, `appearanceMember`, `versionMember`,
  `versionTransitionMember`, `featureMember` (all aggregations, `0..*`).
- Top-level `<group>` declarations become «Union» class boxes
  (`CityModelMemberGroup` → `core:CityModelMember` <<Union>>).

### Stereotype rules (step 06)

- extension chain reaches `gml:AbstractFeatureType` → «FeatureType»;
  reaches only `gml:AbstractGMLType` → «ObjectType»; no GML ancestor →
  «DataType» (default convention)
- `simpleType` restricting string with enumeration facets → «Enumeration»;
  with `<union>` → «Union»; any other `simpleType` → «BasicType»
  (heuristic). Simple types are added as new stereotyped class boxes.
- NOT derivable, therefore skipped: «TopLevelFeatureType» (designation,
  no structural trace; would need a manual list) and «CodeList» (external
  OGC dictionaries, absent from the schema)
- property wrappers and ADE hooks get no stereotype
- relations FeatureType → DataType are not drawn as relations when the
  DataType target is concrete; they are rendered as private members
  (`- name : Type [card]`) inside the owning class box, hideable via
  `hide private members`. Relations to abstract DataTypes (e.g.
  `AbstractGenericAttribute`, a placeholder for the generics module)
  stay as arrows

### Relation extraction rules (step 05)

- Attribute with a local `...PropertyType` or anonymous wrapper, by value
  (no `gml:AssociationAttributeGroup`) → composition, source cardinality `1`
- Same but by reference (`gml:AssociationAttributeGroup` present) →
  aggregation if target is a Feature (descends from `gml:AbstractFeature`
  in the inheritance graph), else dependency
- `gml:ReferenceType` attribute → dependency, target from
  `<appinfo><targetElement>`; same for by-reference anonymous wrappers
  without an inner element ref (e.g. extending
  `gml:AbstractFeatureMemberType`), except those follow the by-reference
  rule (aggregation if the appinfo target is a Feature, else dependency)
- appinfo-derived targets may live in another module: they are promoted
  anyway and drawn as external stub classes (same mechanism as
  external inheritance bases; stub list = external parents ∪ external
  relation targets)
- Target-end cardinality = attribute `min/maxOccurs` (from the XSD);
  source-end cardinality is only labeled for composition (`"1"`, guaranteed
  by XML tree semantics) — by-reference source ends stay unlabeled
  (not derivable from the XSD)
- Promoted attributes leave the class body; relations whose target is
  fixed by an inner element `ref` to a class outside the schema and ADE
  hooks are not promoted (stay as attributes)
- Association-class pattern renders as two hops, e.g.
  `AbstractCityObject *-- CityObjectRelation : relatedTo` +
  `CityObjectRelation ..> AbstractCityObject : relatedTo` Both default to the same output file
(`output/CityGML/3.0/UMLClassDiagram/core.puml`); run the latest step last.

## Candidate next steps (user directs, one at a time)

adding further CityGML modules (all 17 current ones are processed; rerun
`step09_all_packages.py` after any new module to refresh the combined
diagram)

## Main application (`every_class.py`)

`every_class.py` drives the whole pipeline for a data-model schema folder:

    python3 every_class.py <model_folder> [--core <schema_name>]

Detection rules (established with the user):

- The argument is the data-model folder NAME (e.g.
  `schemas/xsds/citygml`); it may contain multiple versions of the same
  data model — all of them are processed.
- External namespaces are NOT considered unless their schemas are
  deliberately stored in the same folder: step 02's import resolution
  is scoped to the given folder via `step02_inheritance.SEARCH_ROOT`
  (module-level, default `schemas/` for standalone step runs).
- DataModel display name via `NAME_MAP` in step 01
  (citygml → CityGML, gml → GML, indoorgml → IndoorGML, infragml →
  InfraGML, kml → KML, pipelineml → PipelineML, xlink → XLink, filter →
  Filter, georss → GeoRSS), fallback: capitalized folder name.
- Version = nearest ancestor directory matching `\d+(\.\d+)*`; ALL
  versions found in the folder are processed, each into its own
  `output/<DataModel>/<Version>/UMLClassDiagram/` (e.g. citygml yields
  2.0 and 3.0 side by side).
- Every `.xsd` in the folder becomes one package — module schemas,
  InfraGML parts (part0–7 dirs just group files), and bundled external
  dependencies placed in the same folder (e.g. kml's
  `atom-author-link.xsd`) alike. Same-stem files in one version get the
  parent dir prefixed to the .puml name (collision guard).
- Core schema resolution order: `--core` argument (stem or file name;
  non-matching versions fall back with a note) → file named
  core/base/`<model>`core/`<model>`base (matches core.xsd,
  cityGMLBase.xsd, indoorgmlcore.xsd) → the only schema of the version →
  interactive numbered prompt. There is ALWAYS a core: if none is found
  structurally, the user designates one. The core's namespace prefix is
  passed to step 09 as the center package for the connectivity layering.
- Processing order is topological over `<import>` namespaces resolved
  within the same version group (dependencies first; cycles fall back
  to alphabetical). Per package it runs steps 01–08 in order (each
  overwrites the same .puml with a richer diagram), then step 09 once
  per version.

Step 09 accepts `[scan_dir] [output_path] [center_package]` (center
defaults to `CENTER_PACKAGE = "core"`); its output-path default is now
`<scan_dir>/all_packages.puml`.

Verified runs (2026-07-29): citygml (2.0: 13 packages, core
cityGMLBase.xsd; 3.0: 17 packages — byte-identical to the previous
step-by-step outputs, also with folder-scoped resolution), kml (2.2.0 +
2.3, ogckml2x picked as core), indoorgml (1.0 + 1.1, indoorgmlcore.xsd
auto-detected), infragml (15 part files, part0's core.xsd), pipelineml
(single schema, auto-core).

Known limitations: steps 05's appinfo lookup hardcodes the GML 3.2
namespace (CityGML 2.0's GML 3.1.1 appinfo is not read); standalone
step runs search `schemas/` from the CWD (every_class.py scopes this to
the given folder), so run from the repo root; InfraGML module titles
show the part dir as family ("Part0 - 1.0 - ...") — cosmetic only.
