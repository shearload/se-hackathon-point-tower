"""Reopen a completed .blend, verify scene geometry and make render paths portable."""
from pathlib import Path
import json
import bpy

HERE=Path(__file__).resolve().parent
OUT=HERE if (HERE/'point_tower_option_a.blend').exists() else HERE.parent/'tower_blender'
expected=[('01 Structural - translucent floors','structural_hero.png',40),
          ('02 Architectural - studio model','studio_hero.png',40),
          ('03 Outrigger - isolated detail','outrigger_detail.png',0)]
checks=[]
for name,filename,floor_count in expected:
    scene=bpy.data.scenes[name]
    columns=[o for o in scene.objects if 'source_node' in o]
    members=[o for o in scene.objects if 'role' in o]
    floors=[o for o in scene.objects if 'floor_elevation_ft' in o]
    walls=[o for o in scene.objects if 'wall_thickness_in' in o]
    assert len(columns)==28 and len(members)==48 and len(floors)==floor_count and len(walls)==4
    assert sum(o['is_outrigger_column'] for o in columns)==8
    assert sum(o['role']=='diagonal' for o in members)==32
    assert sum(o['role'] in ('top_chord','bottom_chord') for o in members)==16
    assert all(abs(o['section_side_in']-(18 if o['role']=='diagonal' else 36))<1e-6 for o in members)
    bounds=scene['projected_camera_bounds']
    assert min(bounds)>0 and max(bounds)<1
    scene.render.filepath='//'+filename
    checks.append(dict(scene=name,columns=28,outrigger_columns=8,chords=16,diagonal_segments=32,
                       slabs=floor_count,core_walls=4,all_geometry_within_camera=True))
assert 'SOURCE_floorplate.json' in bpy.data.texts and 'SOURCE_truss_assembly.json' in bpy.data.texts
bpy.context.window.scene=bpy.data.scenes[expected[0][0]]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'point_tower_option_a.blend'),compress=True)
(OUT/'blender_validation.json').write_text(json.dumps(dict(blender=bpy.app.version_string,
    source_inputs_embedded=True,relative_render_paths=True,checks=checks,
    note='Colours, translucency, display crop and edge softness are visualization only.'),indent=2)+'\n')
print('BLENDER VALIDATION PASSED: three scenes, original structural counts/sections, embedded inputs and portable render paths.')
