# Tower Floorplate Viewer

A Windows desktop viewer for tower floorplate JSON models. The application combines a WPF shell, WebView2, and Three.js to display structural geometry and analysis data. The viewer is organized so file parsing, external-module execution, and rendering remain separate as the app grows.

## What it does

- Opens a building JSON directly, or starts from a CSV with **Select Starting Values**. The latter runs `EXEs/tower_floorplate_generator.exe`, receives an output-folder path, then lets the user choose a building JSON from that folder.
- Renders floor plate polygons as diaphragms and displays columns, beams, shear walls, and outriggers with their modeled section dimensions.
- Provides plan, elevation, and 3D camera controls. The diaphragm thickness is currently fixed at 8 inches.
- Imports load JSON through `EXEs/LoadImporter.exe`. Load view displays global-X story loads as arrows with magnitude labels.
- Loads analysis/optimization result JSON and offers default, loads, deformed-shape, and scalar-color view modes. Results can be selected by load case and geometry candidate.

## Analysis results support

The example `../optimizer_output.example.json` contains load cases and geometry candidates (`none`, `floors_2`, `floors_3`). Candidate names are treated as labels; candidates are associated with the original geometry and optimizer alternatives by their sequence in the results data. Alternate geometry is built using candidate floor-type/occupied-story metadata.

The example results provide story-level `ux_in`, `uy_in`, and `rz_rad` responses, not finite-element mesh-node displacements or local member forces. For display, each model node uses the nearest story response with no interpolation. Deformation is magnified 1000x. Displacement-based coloring is a visualization derived from those story responses; story-drift coloring uses the available drift values. Other color menu entries, such as member DCR, are examples/placeholders when the source results do not contain that quantity.

**Run Analysis** invokes `EXEs/Analysis.exe` with the `analyze` command, building input, loads input, and an output location. The adapter and executable interface are still being validated; the most recently reported run returned exit code 2. Loading a saved result JSON is available independently of running the executable.

## Build and publish

Requirements: .NET 8 SDK to build and Microsoft Edge WebView2 Evergreen Runtime on the target machine. The runtime is an accepted prerequisite for distribution.

From this directory:

```powershell
dotnet publish .\TowerFloorplateViewer.csproj -c Release -p:PublishProfile=win-x64
```

The self-contained, single-file `win-x64` executable is written under `bin\Release\net8.0-windows\win-x64\publish\TowerFloorplateViewer.exe`. Viewer assets and Three.js modules are embedded and extracted under `%LOCALAPPDATA%\TowerFloorplateViewer\Web` at launch. External modules from the repository-level `EXEs` folder are copied beside the published executable into its `EXEs` folder. Generated publish output is excluded from Git; build locally or distribute the published package separately.

## Code organization

- `Models/` defines the parsed floorplate document and structural records.
- `Services/FloorplateJsonService.cs` loads and validates building JSON independently from the UI.
- `Services/LoadModuleService.cs` runs `EXEs/LoadImporter.exe`, parses its per-story loads, and maps them to the loaded floor sequence.
- `Services/AnalysisModuleService.cs` launches the analysis executable and handles the output path/result JSON integration.
- `MainWindow.xaml` and `.xaml.cs` provide the native WPF shell, controls, and bridge to the viewer.
- `Web/viewer.js` owns Three.js geometry, visual modes, and camera behavior; pinned Three.js modules are local dependencies.

Rendered members retain `floorIndex`, `floorType`, `elementId`, and source `nodeRefs` metadata in `userData`. This provides an initial identity seam for mapping model entities/nodes to future meshed-analysis results; mesh-node result mapping is not implemented yet.

## Geometry conventions

- Plan coordinates and story heights are in feet. Section dimensions and diaphragm thickness are in inches.
- Each `floor_sequence` item specifies a floor type and story `floor_height`. Walls and columns span from that story's base to top; beams and outriggers sit at the story top; the diaphragm top is at the same elevation.
- Column `width` and `depth` define the plan footprint. Beam/outrigger `width` is horizontal across the member and `depth` is vertical. A shear wall's `width` is its plan thickness; its connected plan nodes define the wall length.
- The diaphragm polygon is extruded down from the story-top elevation using a fixed 8-inch thickness.

The viewer visualizes model inputs and results; it is not a structural analysis solver. Module interfaces are documented in `../docs/loads-module-contract.md` and `../docs/analysis-module-contract.md`.
