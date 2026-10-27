# SE Hackathon Point Tower

The goal is a multi-step tower design workflow: generate tower geometry, analyze
the building with OpenSees, then optimize outrigger placement using the analysis
results.

SWOOP means **Shear Wall Outrigger Optimization Program**. The project targets a
repetitive design process that often relies on manual guess-and-check. See the
[project overview](docs/SWOOP_PROJECT_OVERVIEW.md) for the motivation, planned
workflow, current implementation status, and limitations.

## Full program workflow

1. **Generate tower geometry.** Read a required `.csv` tower list and write one
   floorplate-format JSON file per tower. This is the implemented first step.
2. **Build and analyze a structural model.** The Windows viewer can run the
   external `Analysis.exe` module with a building JSON and load JSON, or load an
   analysis results JSON directly. The viewer's result reader supports floor
   responses and optimizer candidates. The analysis executable integration is
   still being validated; the latest reported run exited with code 2. A separate
   500-ft OpenSeesPy model prototype is documented under `models/500ft-option-a/`.
3. **Optimize outrigger floors.** Review drift and strength results, evaluate
   candidate outrigger floor locations, add outriggers to the best-performing
   configuration, and rerun the analysis to compare the results. The viewer can
   inspect optimizer candidate results from JSON, but automated candidate search
   and integration with the generator and analysis model remain future work.

The CSV-driven geometry generator and Windows desktop viewer are available. The
full automated generator-analysis-optimization workflow is not yet connected:
the 500-ft model is a separate analysis example, and the viewer's external
analysis-module integration is still being validated.

## Generate tower JSON files

From the project folder, run:

```powershell
python generate_tower_geometry_json.py data/outrigger_tower_list.csv
```

The files are written to `data/tower_floorplate_json/` by default. To choose a
different output folder, pass `--output-dir` (or `-o`):

```powershell
python generate_tower_geometry_json.py data/outrigger_tower_list.csv -o generated_json
```

The generator uses only Python's standard library. The CSV does not specify
structural member sizes or material properties, so the concrete wall and column
properties and perimeter column layout in the output are documented preliminary
assumptions. These JSON files are geometry inputs, not engineered designs.
Floor heights are set uniformly to `Height (ft) / Floors`, so their sum equals
the CSV tower height. CSV fields that have no representation in the documented
floorplate format are not included in the JSON.

## Build a Windows executable

Install the build dependency in the chosen Python environment, then run:

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --onefile --name tower_floorplate_generator generate_tower_geometry_json.py
```

The executable is created at `dist/tower_floorplate_generator.exe`. It accepts
the same input CSV and `--output-dir` arguments as the Python script.

## Windows desktop viewer

`TowerFloorplateViewer/` contains a WPF desktop app that uses WebView2 to host a
Three.js 3D viewer. It opens tower floorplate JSON, renders structural members
and floor diaphragms, and provides plan/elevation/3D view controls for future
editing workflows.

The **Select Starting Values** button runs
`EXEs/tower_floorplate_generator.exe` on a selected CSV. The generator prints an
output folder; the viewer then asks you to choose a building JSON from that
folder and loads it. **Open JSON…** loads an existing model directly.

The **Import Loads JSON…** button runs `EXEs/LoadImporter.exe`. Load display mode
shows global-X story force arrows and magnitude labels. **Load Results JSON…**
opens an optimizer/analysis output such as
[`optimizer_output.example.json`](optimizer_output.example.json), while **Run
Analysis** invokes `EXEs/Analysis.exe` with the model and load inputs.

The results selectors list the load cases and geometry candidates in the results
file. The first candidate is paired with the loaded original model; later
candidates use the optimizer floor types and candidate metadata. The current
example provides floor-level `ux`, `uy`, and `rz` responses rather than finite
element nodal displacements. Deformed view applies the nearest floor's rigid
in-plane motion without interpolation and magnifies it 1000x for visibility.
Displacement coloring derives node movement from those floor responses; story
drift coloring uses the supplied drift values. Member DCR is not included in the
example output.

### Build and run

Requirements: .NET 8 SDK to build and the Microsoft Edge WebView2 Evergreen
Runtime on the machine running the app.

```powershell
cd TowerFloorplateViewer
dotnet publish .\TowerFloorplateViewer.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true
```

The viewer executable is written under
`bin\Release\net8.0-windows\win-x64\publish\`. The external module EXEs are
copied beside it in an `EXEs` folder. The WebView2 Evergreen Runtime remains a
machine-level prerequisite. Generated `bin`, `obj`, and `publish-*` outputs are
excluded from Git; build locally or distribute a published package separately.

See [`TowerFloorplateViewer/README.md`](TowerFloorplateViewer/README.md) for
details on the viewer's code layout, JSON conventions, and module contracts.

## 500 ft tower model

[Model, inputs, results and documentation](models/500ft-option-a/README.md) for the
28-column Option A tower with a concrete core, steel X-braced outriggers and
finite-stiffness floor membranes. Includes a Rhino model with the actual coarse
analysis grid and verified local/global member-force comparisons.

The recorded model uses a coarse mesh only; member sections remain placeholders
pending structural design checks.
