"""Verify the packaged inputs, source syntax, results provenance and file hashes."""
from pathlib import Path
import ast
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parent.parent


def main():
    manifest=json.loads((ROOT/'MANIFEST.json').read_text())
    for item in manifest['files']:
        path=ROOT/item['path']
        assert path.is_file(),item['path']
        assert path.stat().st_size==item['bytes'],item['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],item['path']
    for path in (ROOT/'tower_model').glob('*.py'):
        ast.parse(path.read_text(),filename=str(path))
    inputs=json.loads((ROOT/'tower_floor_mesh_option_a_inputs.json').read_text())
    fp=json.loads((ROOT/inputs['floorplate_file']).read_text())
    assembly=json.loads((ROOT/inputs['truss_assembly_file']).read_text())
    assert len(fp['floor_sequence'])==40
    assert sum(f['floor_height'] for f in fp['floor_sequence'])==500
    for ft in fp['floor_types'].values():
        nodes={n['id']:n for n in ft['structural_nodes']}
        assert len(nodes)==len(ft['structural_nodes'])
        columns=[e for e in ft['structural_elements'] if e['type']=='column']
        assert len(columns)==28
        assert all(n in nodes for e in ft['structural_elements'] for n in e['nodes'])
    assert len(assembly['arms'])==8 and len(assembly['members'])==48
    layout=inputs['column_layout']
    assert layout['central_bay_center_to_center_ft']==28.25
    assert layout['central_clear_between_column_faces_ft']==25.25
    summary=json.loads((ROOT/'tower_model/results_membrane/option_a/mesh_20ft/summary.json').read_text())
    assert summary['inputs_sha256']==hashlib.sha256((ROOT/'tower_floor_mesh_option_a_inputs.json').read_bytes()).hexdigest()
    assert summary['column_count']==28 and summary['mesh']['total_elements']==12800
    assert summary['reconciliation']['member_comparisons']==240
    assert summary['reconciliation']['max_absolute_force_difference_kip']<1e-4
    assert math.isclose(summary['results'][0]['roof_displacement_in'],summary['results'][1]['roof_displacement_in'],rel_tol=1e-5)
    print(f"Verified {len(manifest['files'])} file hashes; source syntax; 28-column inputs; coarse results; local/global reconciliation.")


if __name__=='__main__':
    main()
