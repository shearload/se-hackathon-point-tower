# Analysis module contract

The viewer starts `EXEs/Analysis.exe` without a shell (with `Analyze.exe` as a
backward-compatible fallback) and invokes its `analyze` subcommand with:

```text
Analysis.exe analyze --input <building-json> --loads <load-json> --output <writable-output-directory>
```

The output directory is a unique run folder under `%LOCALAPPDATA%\TowerFloorplateViewer\AnalysisResults`.
The viewer takes the last non-empty output line as a result path when it points
to a file. It may also prefix the line with `RESULTS_PATH=`, `Results file:`,
or `Output file:`. Relative paths are resolved from the output folder first.
If the module does not print a file path, the viewer searches the output folder
for a JSON containing `optimization_results.candidates`. Diagnostics may be
written to standard error.

The viewer opens the returned JSON file. It expects the optimizer output model
at the root (`floor_sequence`, `floor_types`) and analysis data at
`optimization_results.candidates`. Candidate order is significant: the first
candidate supplies the unchanged-model results; subsequent candidates are paired
with geometry options in sequence. Each candidate contains named `cases`, each
with a `floors` map. Floor responses currently expose `floor_number`,
`elevation_ft`, `ux_in`, `uy_in`, and `rz_rad` (and may include drift and
displacement summary fields).

The viewer uses the loaded building JSON for the default geometry. For each
optimizer candidate it builds an option model from the optimizer `floor_types`
and the candidate's `occupied_stories`, using the selected optimizer model's
floor types to identify the modified type and baseline type. The candidate name
is treated as a label and is not interpreted as a story number.

The current results contain floor-level rigid-body translations and rotations,
not finite-element node displacements. Deformed view applies the nearest floor's
in-plane motion to each floor group without interpolation. It amplifies the
display by 1000x for visibility. Element-node SRSS coloring derives node motion
from those rigid floor transforms; story drift uses `max_drift_resultant`.
Member DCR is not present in this output and therefore has no result coloring.

The `Element node SRSS sum` metric sums the derived in-plane displacement
magnitudes at an element's connected structural nodes.
