# Tower Floorplate Viewer

An extensible Windows desktop viewer for tower floorplate JSON models. The app
uses a WPF host for native file selection and settings, a narrow WebView2 bridge,
and a Three.js scene for the 3D model.

## Build and publish

Requirements: .NET 8 SDK for development and the Microsoft Edge
WebView2 Evergreen Runtime on the machine running the app.

From this directory:

```powershell
dotnet publish .\TowerFloorplateViewer.csproj -c Release -p:PublishProfile=win-x64
```

The self-contained, single-file `win-x64` executable is written under
`bin\Release\net8.0-windows\win-x64\publish\TowerFloorplateViewer.exe`.
The Three.js modules and viewer page are embedded in the executable and quietly
extracted to `%LOCALAPPDATA%\TowerFloorplateViewer\Web` on launch. The
WebView2 Evergreen Runtime remains a machine-level prerequisite, as agreed for
this distribution target.
The external executables in the workspace-level `..\EXEs` folder are copied to
an `EXEs` subfolder beside the published viewer.

## Code organization

- `Models/` defines the parsed floorplate document and its structural records.
- `Services/FloorplateJsonService.cs` loads and validates JSON independently
  from the UI.
- `Services/LoadModuleService.cs` runs `EXEs/LoadImporter.exe`, parses its
  per-story forces, and maps them to the loaded floor sequence.
- `Services/AnalysisModuleService.cs` launches `EXEs/Analyze.exe` with the
  building and load JSON paths and records the output path without reading the
  results file.
- `MainWindow.xaml` and `.xaml.cs` contain the native WPF shell and the narrow
  model/thickness bridge to the 3D page.
- `Web/viewer.js` owns Three.js geometry and camera behavior; the pinned
  `three.module.js`, `three.core.js`, and `OrbitControls.js` files are local
  dependencies resolved through the page's import map.

Rendered members retain `floorIndex`, `floorType`, `elementId`, and source
`nodeRefs` in `userData`. This is an initial identity seam for a future analysis
result adapter; it does not yet parse mesh-analysis results.

## Geometry conventions

- Plan coordinates and story heights are in feet; section dimensions and
  diaphragm thickness are in inches.
- A floor sequence entry's `floor_height` is a story increment. Its structural
  walls and columns run from that story's base to top; beams and outriggers sit
  at the story top; the diaphragm top is at that same level.
- Column `width` and `depth` define its plan footprint. Beam/outrigger `width`
  is horizontal across the member and `depth` is vertical. Shear-wall `width`
  is plan thickness and the distance between its connected plan nodes defines
  its in-plane length.
- Diaphragm thickness is a single user setting applied to every floor plate.
  The polygon is extruded down from the story-top elevation.

This is a visualization and input-validation tool, not an analysis solver.
The external module interface is documented in `docs/loads-module-contract.md`.
The analysis module path contract is in `docs/analysis-module-contract.md`.
