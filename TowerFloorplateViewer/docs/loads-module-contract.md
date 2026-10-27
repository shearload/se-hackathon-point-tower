# Load importer module contract

## Invocation

Place `LoadImporter.exe` in the workspace-level `EXEs` folder. The viewer also
checks an `EXEs` folder beside its own executable. It starts the program without
a shell and passes the selected load-input JSON path as its only argument:

```text
LoadImporter.exe "C:\path\to\load-input.json"
```

The process runs hidden, has a five-minute limit, and must exit with code zero.
The viewer captures standard output and standard error. Standard output must
contain one JSON object; a warning line before the JSON is preserved and shown
as a viewer warning. Diagnostics should go to standard error.

## Output JSON

The current ELF importer returns a `story_forces_kip` object whose string keys
are one-based floor numbers and whose numeric values are signed force
magnitudes in kips:

```json
{
  "story_forces_kip": {
    "1": 0.0199,
    "2": 0.0796
  }
}
```

Positive values point in global `+X`; negative values point in global `-X`.
The output field name fixes the force unit to kip. Future load modules should
use an explicit output field and contract like this rather than relying on
console formatting.

## Viewer placement

For each result floor that exists in the loaded `floor_sequence`, the viewer
places one arrow at the area centroid of that floor plate and at that story's
top elevation. The magnitude label is a 2D screen annotation. Arrow length is
scaled linearly against the largest magnitude in the imported result set, with
a small visible minimum for very small nonzero forces; the longest arrow is
capped relative to the floor plate size. Results for floors not represented by
the loaded tower model are skipped and reported in status.

## Adding another executable module

Keep each future executable in `EXEs`. The viewer's process-launch and
visualization services are separate from the WPF controls so new module
contracts can be added without putting process handling into the view layer.
