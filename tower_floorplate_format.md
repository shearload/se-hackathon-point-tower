# Tower Floorplate JSON Format

This document describes the example format in `tower_floorplate_example.json`.
The JSON stores reusable floor plate definitions separately from the sequence of
floor types used from the bottom of the tower upward.

## Coordinate and property units

The top-level `units` object declares the units used throughout the file:

| Property | Meaning | Example unit |
| --- | --- | --- |
| `coordinates` | Plan node coordinates `x` and `y` | `ft` |
| `floor_height` | Vertical height assigned to each floor sequence entry | `ft` |
| `force` | Magnitudes in imported load results | `kip` |
| `section_dimensions` | `section_dims.width` and `.depth` | `in` |
| `Fy` | Yield strength or specified material strength | `psi` |
| `E` | Modulus of elasticity | `psi` |
| `poisson_ratio` | Poisson's ratio | Dimensionless |

Use one consistent coordinate origin and axis orientation for every floor type.
In this example, the origin is at the center of both the floor plate and core.

## Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `format_version` | String | Version of this data structure. |
| `units` | Object | Units for coordinates, section dimensions, `Fy`, and `E`. |
| `floor_sequence` | Array of objects | Floor entries listed bottom to top. Each entry contains `type` and `floor_height`. |
| `floor_types` | Object | Definitions keyed by floor type name, such as `A`, `B`, or `C`. |

Each `floor_sequence` entry has a `type` string naming a key in `floor_types`
and a numeric `floor_height` in the declared units. Repeated `type` values
represent repeated floors, and each entry carries its own height. The sum of
these heights gives the total modeled tower height when heights are interpreted
as story-to-story increments.

## Floor type definition

Each `floor_types` entry contains three parts:

| Field | Description |
| --- | --- |
| `structural_nodes` | Nodes available to structural elements on this floor type. |
| `structural_elements` | Columns, shear walls, or outriggers connecting the structural nodes. |
| `floor_plate` | Separate boundary nodes and their ordered closed-loop polygon. |

### Structural nodes

Each structural node has a unique `id` within its floor type and numeric `x` and
`y` coordinates in the declared coordinate units. Structural element references
must point to IDs in this node list.

### Structural elements

Each element has an `id`, a `type`, a `nodes` array, and the material and section
properties below:

| Field | Description |
| --- | --- |
| `type` | `column`, `beam`, `shear_wall`, or `outrigger`. |
| `nodes` | One node ID for a column; two node IDs for a beam, shear wall, or outrigger. |
| `material_name` | Material label, such as `Concrete` or `Steel`. |
| `section_name` | Section label. |
| `Fy` | Yield strength or specified material strength in the declared `Fy` units. |
| `E` | Modulus of elasticity in the declared `E` units. |
| `poisson_ratio` | Dimensionless Poisson's ratio. |
| `section_dims` | Object with numeric `width` and `depth` in the declared section dimension units. |

The sample uses `Fy: 4000` psi for concrete as the required strength field. For
other concrete conventions, document the intended meaning of `Fy` consistently
or consider renaming it to a general `strength` field in a later format version.
In the sample wall sections, `width` is the 12-inch wall thickness and `depth`
is the 240-inch in-plane wall length.

### Floor plate polygon

`floor_plate.boundary_nodes` is a separate set of plan points. The
`boundary_loop` array lists their IDs in perimeter order. The final edge is
implicitly drawn from the last ID back to the first, so the loop should not
repeat its first ID at the end. The sample polygon is a square 80 feet on each
side.

## Example geometry

The example defines one floor type, `A`, and uses it for one 13-foot-high level
with `floor_sequence: [{"type": "A", "floor_height": 13.0}]`. The structural nodes include the four corners of a
centered 20-foot square core and four column locations 10 feet radially outward
from those corners. Four 12-inch concrete shear-wall elements connect adjacent
core nodes. Each column is connected to its nearest core corner by an 18-by-48
inch concrete beam. The independent floor plate boundary is a centered 80-foot
square.
