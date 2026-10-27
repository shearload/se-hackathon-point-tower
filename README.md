# SE Hackathon Point Tower

Generate one floorplate-format JSON file for each tower row in the required
`.csv` input file. The program prints the resolved JSON output directory and
each output file path to the terminal.

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

## 500 ft tower model

[Model, inputs, results and documentation](models/500ft-option-a/README.md) for the
28-column Option A tower with a concrete core, steel X-braced outriggers and
finite-stiffness floor membranes. Includes a Rhino model with the actual coarse
analysis grid and verified local/global member-force comparisons.

The recorded model uses a coarse mesh only; member sections remain placeholders
pending structural design checks.
