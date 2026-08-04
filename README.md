# every-class : of the geospatial world, be unified!

![every-class banner](docs/images/every-class-banner.jpeg)

This repository turns the XSD schemas of complex data models in the geospatial domain into UML Class Diagrams, with one goal: human & computer readability. The same PlantUML source renders into clean diagrams that specialists can read, navigate and print, while remaining structured plain text that computer systems can parse, compare and process automatically.

## Data models

The generated PlantUML sources (`.puml`) live under
`docs/output/<DataModel>/<Version>/UMLClassDiagram/`:

- **CityGML** — 2.0 (13 packages) and 3.0 (17 packages)
- **GML** — 3.1.1 (31 packages) and 3.2.1 (29 packages)
- **IndoorGML** — 1.1 (2 packages)
- **InfraGML** — 1.0 (15 packages, part0–part7)
- **XPlanung** — 6.1 (8 packages)

Each version folder contains one diagram per package plus a combined
`all_packages` diagram.
