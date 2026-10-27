# Input files and units

The final model uses three root-level JSON files. The floorplate file retains
the supplied format version 1.0. The truss and membrane sidecars explicitly
carry information that a plan-only floor definition cannot encode.

| File | Purpose |
| --- | --- |
| `tower_floorplate_500ft_option_a.json` | Floor sequence, wall/column/chord plan geometry, material and section records, outside floor polygon |
| `tower_500ft_option_a_truss_assembly.json` | Explicit 3D truss connectivity, shared X crossings, wall-end and column references |
| `tower_floor_mesh_option_a_inputs.json` | Slab properties, in-plane modifier, mesh target, loads/mass and floor interface behavior |

The final driver resolves these paths relative to the project artifact
directory. Keep that relationship if moving the project within a repository.

## Floorplate format 1.0

The original top-level fields are unchanged:

```text
format_version: "1.0"
units: coordinates=ft, floor_height=ft, section_dimensions=in, Fy=psi, E=psi
floor_sequence: [{type, floor_height}, ...]
floor_types: {A: {...}, B: {...}, C: {...}}
```

Each reusable floor type has `structural_nodes`, `structural_elements` and
`floor_plate`. Structural nodes have local string IDs and numeric x/y plan
coordinates. An element has `id`, `type`, `nodes`, `material_name`,
`section_name`, `Fy`, `E`, `poisson_ratio` and `section_dims` (`width`, `depth`).
Columns reference one plan node; walls and horizontal chords reference two.
For concrete, the required field named `Fy` holds specified f'c, not tensile
yield strength. Wall `width` is thickness and `depth` is centerline plan length.

Forty explicit 12.5 ft sequence entries define 500 ft total height. Type A is
typical, B adds eight bottom chords at the **top of Level 26**, and C adds eight
top chords at the **top of Level 28**. Other floors use A. Do not interpret a
chord record as a member extending over the story height.

S nodes locate the core wall centerline corners, C nodes locate the 28 column
centerlines and F nodes locate the eight physical wall-end attachments. Node
IDs are local to a floor definition; an importer needs unique analysis tags
for each level. Unused F nodes on typical floors are attachment metadata,
not free analysis nodes.

`floor_plate.boundary_nodes` is separate from structural nodes. Its
`boundary_loop` lists outside corners in perimeter order with implicit final
closure, without repeating the first ID. This v1 field has no void-loop
support; the final analysis derives the clear core opening from wall geometry.

## 3D truss assembly sidecar

`format_version` is `tower_truss_3d_1.0`; coordinates are feet, dimensions inches
and material properties psi. Principal fields are:

- `floorplate_file`: associated v1 floorplate.
- `column_layout`: selected Option A geometry metadata.
- `arms`: eight arm records with axis, wall, physical root, aligned column,
  and bottom/top floors.
- `nodes`: 40 global assembly IDs with x/y/z, arm, plane and role.
- `members`: 48 two-node records with role, section and steel properties.
- `analysis_idealization`: axial truss behavior and crossing restraint basis.

Node suffixes RB/RT identify wall root bottom/top, CB/CT identify column
connection bottom/top, and M identifies the shared X intersection. There are
16 chord records and 32 diagonal segments. Each of eight M nodes has four
incident diagonal segments. Column verticals are represented by the existing
global columns and are not duplicated as assembly members.

The 16 assembly chords and the B/C floorplate chord records are two
representations of the same members. The global truss builder consumes the
assembly once. An importer must not add both copies to the stiffness model.

The current layout metadata distinguishes:

- `central_bay_center_to_center_ft`: **28.25 ft** between column centerlines.
- `central_clear_between_column_faces_ft`: **25.25 ft** between the faces of
  the 36-in columns.

Earlier metadata called the 28.25 ft distance `central_clear_bay_ft`; that
historical label was corrected without changing geometry, stiffness, loads
or recorded results. The summary explicitly records this metadata-only
correction. The no-columns-between-pair condition applies to column centerline
locations.

## Floor membrane sidecar

`format_version` is `tower_membrane_floor_1.0`. The file references the current
floorplate and truss sidecar and supplies:

- Slab thickness 8 in, f'c 6 ksi, density 150 pcf and Poisson ratio 0.20.
- In-plane stiffness factor 0.70.
- Requested coarse maximum spacing 20 ft. A 10 ft target remains as optional
  future input only; there is no accepted finer-mesh result.
- D = 150 psf including slab, L = 50 psf, mass live fraction 0.25.
- Lateral probe 1,000 kip, distributed in plan by tributary area.
- Retained core gravity fraction 0.50 and explicit membrane-only behavior.
- Core void/interface, column UX/UY connection and crossing restraint notes.

The grid is generated from alignment coordinates and subdivided to respect
the requested maximum spacing. Actual intervals can be smaller: the recorded
coarse maximum is 16.8056 ft. Input JSON does not directly list shell nodes or
connectivity; the final summary records the generated coordinate grid and
counts. `tower_500ft_option_a_membrane.3dm`, generated by
`tower_model/export_membrane_rhino.py`, reproduces that actual grid as 40 floor
meshes. Its layer `10 Coarse analytical floor mesh - toggle visibility` is
initially hidden. The optional base `tower_500ft_option_a.3dm` contains generic
display floor ring meshes, which are not the analytical discretization.

## Edit, run and audit

Edit inputs deliberately, then rerun the final entry point:

```powershell
python tower_model/tower_membrane.py --spacing 20 --inputs tower_floor_mesh_option_a_inputs.json
```

The current reader assumes square, uniform core/floor geometry, equal story
heights and uniform steel properties consistent with the recorded inputs.
The formats are project input conventions, not a general-purpose validated
structural schema. Reference and area assertions catch common mistakes but
do not validate structural adequacy. Recorded results apply to the recorded
inputs; a geometry/material/load change requires new results.
