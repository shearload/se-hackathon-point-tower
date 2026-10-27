# External modules

Place command-line module executables in this shared `EXEs` folder. The tower
viewer looks for `tower_floorplate_generator.exe`, `LoadImporter.exe`, and `Analysis.exe` here and in an `EXEs`
folder beside its own executable. It accepts `Analyze.exe` as a legacy analysis
module name. When publishing the viewer project, executables in this
folder are copied into the published app's `EXEs` subfolder.

The load module contract is documented at
`TowerFloorplateViewer/docs/loads-module-contract.md`.
The analysis module contract is at
`TowerFloorplateViewer/docs/analysis-module-contract.md`.
`tower_floorplate_generator.exe` accepts one CSV path and prints its output file
or folder path. When it returns a folder, the viewer prompts for a building JSON
inside that folder and loads the selected file as the active model.
