"""Run with Blender --background --python this_file -- [--draft].

Exact input coordinates are converted ft/in -> metres. Floors are centered on
analysis levels. Ghost floors, isolated zone, colours and edge bevels are display
treatments; no facade, connection hardware or revised structural sizes are added.
"""
from pathlib import Path
import json
import math
import sys
import hashlib
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parent.parent
PACKAGED=Path(__file__).resolve().parent.name=='visualization' and (ROOT/'tower_floorplate_500ft_option_a.json').exists()
ARTIFACT=ROOT if PACKAGED else ROOT/'se-hackathon-point-tower/models/500ft-option-a'
OUT=Path(__file__).resolve().parent if PACKAGED else ROOT/'tower_blender'
OUT.mkdir(exist_ok=True)
FP=ARTIFACT/'tower_floorplate_500ft_option_a.json'
TRUSS=ARTIFACT/'tower_500ft_option_a_truss_assembly.json'
fp=json.loads(FP.read_text())
assembly=json.loads(TRUSS.read_text())
DRAFT='--draft' in sys.argv
GPU=False
GPU_NAME='CPU'
prefs=bpy.context.preferences.addons['cycles'].preferences
for backend in ('OPTIX','CUDA','HIP','ONEAPI'):
    try:
        prefs.compute_device_type=backend
        prefs.get_devices()
        devices=[d for d in prefs.devices if d.type==backend]
        if devices:
            for d in prefs.devices: d.use=d in devices
            GPU=True
            GPU_NAME=', '.join(d.name for d in devices)
            break
    except Exception:
        pass
print('RENDER DEVICE '+GPU_NAME,flush=True)
FT=0.3048
IN=0.0254
H=500*FT
B=(220+11/12)*FT
CORE=31.25*FT
WALL=36*IN


def material(name,color,metal=0,roughness=0.5,ghost=0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1-ghost)
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    nodes.clear()
    out=nodes.new('ShaderNodeOutputMaterial')
    p=nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal
    p.inputs['Roughness'].default_value=roughness
    if ghost:
        transparent=nodes.new('ShaderNodeBsdfTransparent')
        mix=nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value=ghost
        mat.node_tree.links.new(p.outputs['BSDF'],mix.inputs[1])
        mat.node_tree.links.new(transparent.outputs[0],mix.inputs[2])
        mat.node_tree.links.new(mix.outputs[0],out.inputs['Surface'])
    else:
        mat.node_tree.links.new(p.outputs['BSDF'],out.inputs['Surface'])
    return mat


def coll(scene,name):
    c=bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


def cube(name,low,high,collection,mat,bevel=0):
    x0,y0,z0=low; x1,y1,z1=high
    verts=[(x,y,z) for z in (z0,z1) for y in (y0,y1) for x in (x0,x1)]
    faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new('Subtle presentation edge softness','BEVEL')
        mod.width=bevel
        mod.segments=2
    return obj


def member(name,start,end,side,collection,mat):
    a,b=Vector(start),Vector(end)
    length=(b-a).length
    obj=cube(name,(-side/2,-side/2,-length/2),(side/2,side/2,length/2),collection,mat,0.007)
    obj.location=(a+b)/2
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    obj['section_side_in']=side/IN
    obj['steel_Fy_ksi']=50
    obj['start_ft']=[v/FT for v in a]
    obj['end_ft']=[v/FT for v in b]
    return obj


def slab(name,z,collection,mat):
    # Closed ring with actual 8-in thickness and the clear core opening.
    out=B/2; inner=CORE/2-WALL; t=8*IN
    ring=[(-out,-out),(out,-out),(out,out),(-out,out),
          (-inner,-inner),(inner,-inner),(inner,inner),(-inner,inner)]
    verts=[(x,y,z+dz) for dz in (-t/2,t/2) for x,y in ring]
    faces=[]
    for i in range(4):
        j=(i+1)%4
        faces += [(i,j,j+4,i+4),(i+8,i+12,j+12,j+8),
                  (i,i+8,j+8,j),(i+4,j+4,j+12,i+12)]
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],[tuple(reversed(face)) for face in faces])
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    mesh.materials.append(mat)
    obj['thickness_in']=8
    obj['floor_elevation_ft']=z/FT
    return obj


def curve_loop(name,pts,collection,mat,radius):
    data=bpy.data.curves.new(name,'CURVE')
    data.dimensions='3D'
    data.resolution_u=1
    data.bevel_depth=radius
    data.bevel_resolution=0
    line=data.splines.new('POLY')
    line.points.add(len(pts)-1)
    for point,xyz in zip(line.points,pts):
        point.co=(*xyz,1)
    line.use_cyclic_u=True
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def camera(scene,collection,name,location,target,points):
    data=bpy.data.cameras.new(name)
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    obj.location=location
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO'
    data.ortho_scale=220
    data.clip_start=0.1; data.clip_end=2000
    scene.camera=obj
    bpy.context.view_layer.update()
    projected=[world_to_camera_view(scene,obj,Vector(p)) for p in points]
    dx=max(p.x for p in projected)-min(p.x for p in projected)
    dy=max(p.y for p in projected)-min(p.y for p in projected)
    data.ortho_scale*=max(dx/0.80,dy/0.86)
    scene.view_layers[0].update()
    projected=[world_to_camera_view(scene,obj,Vector(p)) for p in points]
    bounds=[min(p.x for p in projected),max(p.x for p in projected),min(p.y for p in projected),max(p.y for p in projected)]
    assert bounds[0]>0.03 and bounds[1]<0.97 and bounds[2]>0.03 and bounds[3]<0.97,bounds
    scene['projected_camera_bounds']=bounds
    return obj


def area(scene,collection,name,loc,target,power,size,color):
    light=bpy.data.lights.new(name,'AREA')
    light.energy=power
    light.shape='DISK'
    light.size=size
    light.color=color
    obj=bpy.data.objects.new(name,light)
    collection.objects.link(obj)
    obj.location=loc
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def create_scene(name,studio=False,detail=False):
    scene=bpy.data.scenes.new(name)
    bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC'
    scene.unit_settings.length_unit='METERS'
    scene.render.engine='CYCLES'
    scene.cycles.device='GPU' if GPU else 'CPU'
    scene.cycles.samples=12 if DRAFT else 64
    scene.cycles.use_denoising=True
    scene.cycles.adaptive_threshold=0.06 if DRAFT else 0.025
    scene.cycles.max_bounces=6
    scene.cycles.transparent_max_bounces=48
    scene.render.threads_mode='FIXED'
    scene.render.threads=8
    scene.render.resolution_x=1800 if detail else 1400
    scene.render.resolution_y=1150 if detail else 1800
    scene.render.resolution_percentage=50 if DRAFT else 100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX'
    try: scene.view_settings.look='AgX - Medium High Contrast'
    except TypeError: pass
    world=bpy.data.worlds.new(name+' studio world')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.81,0.84,0.85,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.45
    scene.world=world
    collections={key:coll(scene,key) for key in ['01 Concrete core','02 Perimeter columns','03 Steel outriggers','04 Floor plates','05 Floor edge lines','06 Studio lighting','07 Cameras','08 Display ground']}
    core_mat=material(name+' concrete',(0.63,0.60,0.53) if studio else (0.16,0.38,0.40),roughness=0.72)
    column_mat=material(name+' graphite steel',(0.10,0.14,0.18),metal=0.35,roughness=0.36)
    outrigger_column_mat=material(name+' outrigger columns',(0.29,0.20,0.12),metal=0.4,roughness=0.38)
    truss_mat=material(name+' highlighted steel',(0.69,0.29,0.065),metal=0.5,roughness=0.30)
    floor_mat=material(name+' floor plates',(0.69,0.71,0.70) if studio else (0.58,0.73,0.78),roughness=0.65,ghost=0 if studio else 0.985)
    edge_mat=material(name+' subtle floor edges',(0.28,0.43,0.48),roughness=0.6,ghost=0.35)
    ground_mat=material(name+' display ground',(0.79,0.81,0.81) if not studio else (0.82,0.80,0.75),roughness=0.8)
    z0,z1=(310*FT,365*FT) if detail else (0,H)
    half=CORE/2; inner=half-WALL
    for label,low,high in [
        ('South',(-half,-half,z0),(half,-inner,z1)),
        ('North',(-half,inner,z0),(half,half,z1)),
        ('West',(-half,-inner,z0),(-inner,inner,z1)),
        ('East',(inner,-inner,z0),(half,inner,z1))]:
        ob=cube(label+' core wall',low,high,collections['01 Concrete core'],core_mat,0.012)
        ob['wall_thickness_in']=36; ob['concrete_fc_ksi']=8
    nodes={n['id']:n for n in fp['floor_types']['A']['structural_nodes']}
    outriggers={a['column_node_id'] for a in assembly['arms']}
    for e in fp['floor_types']['A']['structural_elements']:
        if e['type']!='column': continue
        n=nodes[e['nodes'][0]]
        x,y=n['x']*FT,n['y']*FT
        s=e['section_dims']['width']*IN
        ob=cube(e['id'],(x-s/2,y-s/2,z0),(x+s/2,y+s/2,z1),collections['02 Perimeter columns'],outrigger_column_mat if n['id'] in outriggers else column_mat,0.008)
        ob['source_node']=n['id']; ob['section_side_in']=36
        ob['is_outrigger_column']=n['id'] in outriggers
    pts={n['id']:(n['x']*FT,n['y']*FT,n['z']*FT) for n in assembly['nodes']}
    for e in assembly['members']:
        ob=member(e['id'],*(pts[n] for n in e['nodes']),e['section_dims']['width']*IN,collections['03 Steel outriggers'],truss_mat)
        ob['role']=e['role']; ob['arm_id']=e['arm_id']
    if not detail:
        for k in range(1,41):
            z=k*12.5*FT
            slab_obj=slab(f'L{k:02d} - 8in slab',z,collections['04 Floor plates'],floor_mat)
            if not studio:
                slab_obj.visible_shadow=False
            if not studio:
                r=B/2
                curve_loop(f'L{k:02d} perimeter',[(x,y,z) for x,y in [(-r,-r),(r,-r),(r,r),(-r,r)]],collections['05 Floor edge lines'],edge_mat,0.018)
        cube('Studio display ground',(-1500,-1500,-0.12),(1500,1500,-0.04),collections['08 Display ground'],ground_mat)
    else:
        # This scene is a clearly labeled isolation, with coordinates unchanged.
        scene['display_isolation']='Core and columns cropped to 310-365 ft; floors hidden to reveal trusses.'
    target=(0,0,(z0+z1)/2)
    bound=[(x,y,z) for x in (-B/2-0.5,B/2+0.5) for y in (-B/2-0.5,B/2+0.5) for z in (z0,z1)]
    if detail:
        camloc=(140,-180,205)
    else:
        camloc=(205,-270,185)
    cam=camera(scene,collections['07 Cameras'],name+' camera',camloc,target,bound)
    area(scene,collections['06 Studio lighting'],'Large warm key',(60,-85,210),target,320000,80,(1.0,0.92,0.81))
    area(scene,collections['06 Studio lighting'],'Cool fill',(-100,-25,145),target,180000,100,(0.77,0.88,1.0))
    area(scene,collections['06 Studio lighting'],'Soft rim',(35,100,185),target,400000,65,(1.0,0.96,0.89))
    scene['reference_height_ft']=500
    scene['column_count']=28; scene['outrigger_columns']=8; scene['truss_arms']=8
    scene['source_floorplate_sha256']=hashlib.sha256(FP.read_bytes()).hexdigest()
    scene['source_truss_sha256']=hashlib.sha256(TRUSS.read_bytes()).hexdigest()
    scene['visualization_note']='True source geometry, metric conversion. Colours and translucency are display choices; member sizes are placeholders, not designed capacities.'
    scene['floor_reference']='8 in slabs centered on analysis floor levels'
    assert len(collections['02 Perimeter columns'].objects)==28
    assert len(collections['03 Steel outriggers'].objects)==48
    assert sum(o.get('role')=='diagonal' for o in collections['03 Steel outriggers'].objects)==32
    assert sum(o.get('role') in ('top_chord','bottom_chord') for o in collections['03 Steel outriggers'].objects)==16
    return scene


def main():
    for ob in list(bpy.data.objects): bpy.data.objects.remove(ob,do_unlink=True)
    original=list(bpy.data.scenes)
    scenes=[create_scene('01 Structural - translucent floors'),
            create_scene('02 Architectural - studio model',studio=True),
            create_scene('03 Outrigger - isolated detail',detail=True)]
    bpy.context.window.scene=scenes[0]
    for sc in original: bpy.data.scenes.remove(sc)
    for name,body in [('SOURCE_floorplate.json',FP.read_text()),
                      ('SOURCE_truss_assembly.json',TRUSS.read_text()),
                      ('README - Presentation notes',
                       'Three scenes: structural overview, architectural studio, isolated outriggers.\n'
                       'Geometry uses the approved Option A inputs in metres. Floors are 8 in thick, centered on analysis levels.\n'
                       'Ghost floors, colours, edge softness and isolated-zone clipping are display treatments only.\n'
                       'The detail crops the core/columns to 310-365 ft and omits floors; no members are relocated.\n'
                       'No facade, gussets, anchorage or other connection hardware has been invented.\n'
                       'Steel sizes remain placeholders, not designed capacities.\n')]:
        text=bpy.data.texts.new(name)
        text.write(body)
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'point_tower_option_a.blend'),compress=True)
    names=['structural_hero','studio_hero','outrigger_detail']
    for sc,name in zip(scenes,names):
        sc.render.filepath=str(OUT/(('draft_' if DRAFT else '')+name+'.png'))
        print(f'RENDER START {sc.name} -> {sc.render.filepath}',flush=True)
        bpy.ops.render.render(write_still=True,scene=sc.name)
        print(f'RENDER COMPLETE {name}',flush=True)
    bpy.context.window.scene=scenes[0]
    for sc,name in zip(scenes,names):
        sc.render.filepath='//'+name+'.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'point_tower_option_a.blend'),compress=True)
    (OUT/'scene_metadata.json').write_text(json.dumps(dict(blender_version=bpy.app.version_string,
        source_floorplate=FP.name,source_truss=TRUSS.name,height_m=H,plan_m=B,
        scenes=[s.name for s in scenes],columns=28,outrigger_columns=8,truss_arms=8,
        chord_members=16,diagonal_segments=32,floor_thickness_m=8*IN,
        floor_reference='slabs centered at analysis floor elevations',
        isolated_detail='core/column display crop 310-365 ft; floors omitted; no geometry moved',
        draft=DRAFT,render_device=GPU_NAME),indent=2)+'\n')


if __name__=='__main__': main()
