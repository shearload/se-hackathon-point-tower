# Revision history and superseded files

The current entry point is `tower_model/tower_membrane.py` with the **Option A
28-column inputs** and coarse results under
`tower_model/results_membrane/option_a/mesh_20ft/`.

## Earlier conceptual beam-arm model

The first model had a 500 ft core/spine, 16 perimeter columns and four single
elastic steel beam arms around Level 27. The user's H/B = 16 instruction set
the core outside width to 31.25 ft, superseding the drawing's 100 ft dimension.
This version did not represent the requested paired multi-story steel trusses.
`tower.py` contains the original standalone main as well as reusable routines;
running that main does not select the final model.

## Paired X-braced trusses with rigid floors

The system was revised to eight wall-end arms in four planes, with top/bottom
chords at 350/325 ft and connected X crossings. Eight columns were moved into
wall alignment while retaining 16 columns total. Diagonals became 18-in
solid-square placeholders and chords became 36-in squares, with Fy = 50 ksi.
Whole-floor rigid diaphragms bypassed the horizontal chords, producing nearly
zero chord axial demand. These rigid-floor results are not current sizing
results.

## Earlier one-way local assessment

A separate local model imposed global root translations and column vertical
translations, while freeing column horizontal motion. It produced nonzero
chord forces but did not feed redistributed forces back into the global model.
Its reported peaks of approximately 1.75/1.90/7.87 ksi for top chords, bottom
chords and diagonals belong to that earlier approximation and layout. The
standalone main in `local_truss.py` runs that older assessment; the current
driver imports only its local solver for a different, same-model cut check.

## Finite floor membranes, then Option A columns

The user specified 8-in, 6-ksi, 150-pcf concrete floors with 70% gross in-plane
stiffness, retaining the earlier D/L/mass assumptions. Floor-wide rigid
diaphragms were replaced by finite membranes, retaining local core
cross-section constraints. The preliminary finite-floor run still used the
earlier 16-column layout and is superseded.

The user then selected **Option A: 28 columns**. Eight wall-aligned outrigger
columns and corner columns are retained; there are no columns between the
outrigger pair on any face. Each outer side has three equal 32.1111 ft bays.
The central bay is 28.25 ft center-to-center, not clear; actual physical clear
width is 25.25 ft for 36-in columns.

The current coupled coarse model produces roof displacement 2.491833 in and
peak stresses of 1.55998/1.66498/10.43069 ksi for top chords, bottom chords and
diagonals under the documented probe. Local cuts reproduce this same global
model's forces. These values supersede earlier demand summaries.

The user explicitly stopped the finer-mesh run. No completed refinement study
or mesh-converged result is claimed. Earlier geometry, result folders and ZIP
packages may remain as history; their names and contents should not be used
interchangeably with the current Option A inputs/results.

The final geometry deliverable is `tower_500ft_option_a_membrane.3dm`, which
adds the actual coarse analysis grid to the 28-column structural model. The
base `tower_500ft_option_a.3dm` remains an optional structural reference with
generic floor ring surfaces.
