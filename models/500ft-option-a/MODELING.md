# Modeling basis and limits

The final model is a 3D, six-DOF OpenSees domain in **kip–inch–second** units.
Plan coordinates are centered on the core, Z is upward and all base nodes are
fixed. Inputs use feet, inches and psi as declared; conversion occurs in code.

## Concrete core and steel system

The 31.25 ft outside square concrete core has uniform 36-in walls and a 25.25 ft
clear inside dimension. A 3D elastic Timoshenko spine, one element per story,
represents its global axial, biaxial flexural, approximate shear and torsional
stiffness. [ElasticTimoshenkoBeam](https://openseespydoc.readthedocs.io/en/latest/src/ElasticTimoshenkoBeam.html)
is the OpenSeesPy frame formulation used for the core.

For outside width B = 375 in and wall thickness t = 36 in:

- A = B² − (B − 2t)² = 48,816 in².
- Iy = Iz = [B⁴ − (B − 2t)⁴]/12 = 945,541,512 in⁴.
- Approximate closed-section torsion J = t(B − t)³ = 1,402,495,884 in⁴.
- Approximate Avy = Avz = 2t(B − t) = 24,408 in².

The core uses normal-weight Ec = 57,000√f'c in psi, f'c = 8 ksi, Poisson ratio
0.20, and gross bending/shear factors of 1.0. Torsion and shear-area formulas
are simplified section approximations. The spine cannot resolve wall openings,
reinforcement, local wall stresses or anchorage demands.

The 28 steel columns are continuous, fixed-base elastic beam-columns with
36-in solid-square sections. Eight outrigger arms are aligned with the core
walls in four planes: X trusses at Y = +/-14.125 ft and Y trusses at
X = +/-14.125 ft. Their physical roots are at the outside wall ends, 15.625 ft
from the center in the extension direction. Rigid offsets connect these roots
to the spine's core cross-section; these are analytical offsets, not physical
steel members crossing the core void.

Each arm has 36-in solid-square chords at 325 and 350 ft and an X of 18-in
solid-square diagonals. Both diagonals meet at a common crossing at 337.5 ft,
giving four diagonal segments per arm. The existing column forms the outer
vertical; no coincident extra vertical member is added. Chords and braces use
elastic axial [truss elements](https://openseespydoc.readthedocs.io/en/latest/src/trussEle.html),
with steel E = 29,000 ksi and Fy = 50 ksi as reference properties. Truss
rotations are unused; joints are pinned. All steel sizes are placeholders.

## Finite in-plane floor mesh

Floors use [ShellMITC4](https://openseespydoc.readthedocs.io/en/latest/src/ShellMITC4.html)
with an [ElasticMembranePlateSection](https://openseespydoc.readthedocs.io/en/latest/src/elasticMembranePlateSection.html).
The slab has thickness 8 in, f'c = 6 ksi, Poisson ratio 0.20 and normal-weight
gross Ec = 4,415.201 ksi. Applying the user-selected 70% in-plane factor gives
E_effective = 3,090.641 ksi. The same factor acts on membrane normal and shear
stiffness through the isotropic elastic section.

The section's out-of-plane bending modifier is zero. Mesh-node UZ, RX and RY
are restrained; RZ remains available for shell drilling behavior. Thus these
elements supply in-plane diaphragm stiffness only. They do not model flat-plate
bending, punching shear or vertical slab gravity transfer.

The grid aligns with wall faces/centerlines, column positions and crossing
restraint locations. The clear core void is excluded. Mesh nodes in the wall
footprint are constrained to the retained rigid core cross-section using
[rigidDiaphragm](https://openseespydoc.readthedocs.io/en/latest/src/rigidDiaphragm.html).
This constraint is confined to the core, not extended over the floor plate.
The rest of each floor deforms with finite membrane stiffness.

Column and slab in-plane translations are connected by
[equalDOF](https://openseespydoc.readthedocs.io/en/latest/src/equalDOF.html)
on UX/UY only. Column vertical translations and bending rotations remain free
of slab constraints. Truss crossing motion normal to its plane is tied to the
floor membrane at Level 27. In-plane crossing motion is solved by the truss.
Chords retain their end-joint model; distributed composite slab/chord bond and
connection hardware are not modeled.

The requested 20 ft maximum grid spacing becomes 16.8056 ft after alignment.
The recorded mesh has 320 cells and 360 nodes per floor. A one-element axial
patch check reproduced the expected 320 kip reaction and -0.002 in Poisson
contraction. This is an element implementation check, not a mesh-convergence
study. The user stopped the finer-mesh run, so refinement sensitivity remains
unassessed.

The corresponding geometry export is `tower_500ft_option_a_membrane.3dm`:
1,328 closed structural Breps plus 40 floor meshes containing the 12,800
analytical cells. Its actual-grid layer, `10 Coarse analytical floor mesh -
toggle visibility`, is initially hidden. The optional base file
`tower_500ft_option_a.3dm` contains only generic display floor ring surfaces.

## Gravity, mass and lateral loading

The outside plate minus the clear core void gives 48,166.611 ft² per floor.
Retained floor D = 150 psf includes the 8-in slab's 100 psf self-weight at
150 pcf, leaving 50 psf of superimposed dead load. Floor L = 50 psf.
Slab weight is not added a second time. Concrete wall and steel member weights
are added separately using 150 pcf and 490 pcf respectively.

Because slab bending is excluded, gravity continues to use the earlier
assumed load split: 50% of floor D + L to the core and 50% equally among the
28 columns. This is not a tributary-area gravity framing analysis. Vertical
segment self-weight is half-lumped at adjacent nodes, including the fixed
base; truss self-weight is half-lumped at its element ends.

Floor dynamic weight uses D + 0.25L and the modeled member weights assigned
to each floor. The complete floor-level weight is smeared over membrane
nodes by tributary area, divided by g = 386.089 in/s², in UX/UY. Member mass is
therefore not separately retained at its physical locations. Shell density and
element mass are zero to avoid double counting; no explicit vertical dynamic
mass is included. Torsional inertia arises from the spatial nodal masses.

The lateral probe has 1,000 kip total base shear, distributed over height
proportional to floor elevation and across each floor by membrane tributary
area. Independent positive X and Y cases are solved after D + L gravity.
G-X and G-Y movements/forces follow by exact linear superposition from the
gravity and positive-axis solutions. These are illustrative demand cases,
not site hazards, code combinations or a design envelope.

## Analysis, verification and interpretation

The model uses Linear geometry transformations and elastic materials. Sparse
UmfPack is used for global static solution; six modes are obtained with ARPACK.
X/Y modal properties are identical for the unchanged linear model, so the
second-axis run reuses the first-axis periods. Global checks include base shear,
gravity force, overturning including column vertical-force couples, X/Y roof
symmetry and independently calculated total gravity weight.

For same-model cut verification, each five-node arm receives all global wall
and column interface translations, plus the identical member self-weight.
All 240 local member forces agree with the coupled global solution to a maximum
absolute difference of 1.21×10^-11 kip. Local compatibility, force/moment
equilibrium and energy/work checks also pass. This verifies internal consistency
of the model and extraction, not a conservative design bound or validation of
the physical assumptions.

P-delta, yielding, compression buckling, local section instability, nonlinear
cracking, creep, shrinkage, construction sequence, wall openings/reinforcement,
soil/foundation flexibility, connection stiffness and anchorage design are
omitted. Floor membrane peak stresses at point supports may be mesh sensitive
and are not used here for slab or collector design. No steel section, core,
column, floor, connection or out-of-plane restraint has been accepted by a
strength, stability, drift or comfort check.
