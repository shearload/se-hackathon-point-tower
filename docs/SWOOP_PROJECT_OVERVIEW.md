# SWOOP project overview

**SWOOP** is the **Shear Wall Outrigger Optimization Program**. The project aims
to make tall-building lateral-system studies less dependent on repeated manual
guess-and-check. Each new plan can require another cycle of proposing a wall and
outrigger layout, building an analysis model, and reviewing the results. That
iteration is time-consuming, and exploring many geometric and material choices
can become computationally difficult.

The intended program connects tower geometry, structural analysis, and design
search in one workflow. It should accept a floor plan and design parameters,
analyze candidate systems, and produce a shear-wall layout and outrigger
locations that meet the selected design criteria.

## Intended workflow and current status

### 1. Generate tower geometry — implemented

`generate_tower_geometry_json.py` reads a required CSV tower list and creates
one floorplate-format JSON file per tower. The current CSV input is
`data/outrigger_tower_list.csv`. The generator uses the tower name, total height,
core dimensions, footprint dimensions, and floor count. It prints the output
directory and each JSON file path.

The generator applies documented preliminary assumptions for concrete wall and
column properties and perimeter column layout. It divides the total height
uniformly across the floor count. The generated geometry is an analysis input,
not a completed structural design. See the root README for commands and the
`data/sample_floor_plan_structure_template_blank.json` for a JSON template.

### 2. Build and analyze an OpenSees model — prototype exists; integration remains

The target workflow will turn each generated tower geometry into an OpenSeesPy
model, run structural analyses, and collect response measures such as story
drift and member forces or strength-related results. The analysis results must
be available in a consistent form for comparison and optimization.

The repository includes a separate 500-ft Option A OpenSeesPy model and recorded
analysis results under `models/500ft-option-a/`. That prototype demonstrates
modeling and analysis work, but it is not yet called by the CSV geometry
generator and is not a general analysis pipeline for every tower in the list.
The current elastic prototype does not provide final member strength or
stability checks.

### 3. Optimize outrigger locations — planned

The planned optimizer will review analysis results, test candidate outrigger
floor locations, add outriggers to promising configurations, and rerun the
analysis. It will compare drift and strength-related results to identify the
best configuration under defined design criteria.

The automated candidate-floor search is not implemented yet. Before it can
select a best case, the project needs explicit objectives, constraints,
candidate floor ranges, and strength-check methods. The optimizer must also be
connected to both the generated geometry and OpenSees analysis steps.

## Inputs and outputs

The presentation describes an architectural floor plan and user-supplied
parameters as program inputs. The current implementation is narrower: it reads
the tower dimensions and floor counts from the CSV and writes preliminary
floorplate JSON files. No user interface or automatic architectural-plan
import is implemented in the geometry generator.

The intended final outputs are a shear-wall layout and tower/outrigger levels,
supported by analysis results. At present, the CSV generator outputs geometry
JSON only. The separate 500-ft prototype has its own model and results; the
planned end-to-end outputs are not yet produced from the CSV list.

## Development priorities

1. Define and validate the analysis input contract between floorplate JSON and
   the OpenSeesPy model.
2. Generalize the model-building and analysis workflow to accept each generated
   tower, and record drift and member demand results consistently.
3. Define strength and stability checks, optimization objectives, constraints,
   and candidate outrigger floors.
4. Implement the search loop that modifies outrigger locations, reruns analysis,
   and reports the selected configuration and supporting results.
