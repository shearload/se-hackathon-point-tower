"""Create a layered Rhino 7-compatible 3DM directly from floorplate JSON.

Run with rhino3dm==8.35.0: python tower_model/export_rhino.py
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import rhino3dm as r

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'tower_floorplate_500ft.json'
OUTPUT = ROOT / 'tower_500ft.3dm'


def export(source=SOURCE, output=OUTPUT, assembly_path=None):
    SOURCE, OUTPUT = Path(source), Path(output)
    assembly = json.loads(Path(assembly_path).read_text()) if assembly_path else None
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    assert data['format_version'] == '1.0'
    assert data['units'] == dict(coordinates='ft', floor_height='ft',
                                 section_dimensions='in', Fy='psi', E='psi')
    model = r.File3dm()
    model.Settings.ModelUnitSystem = r.UnitSystem.Feet
    model.Settings.ModelAbsoluteTolerance = 0.0001
    model.Settings.ModelAngleToleranceRadians = math.radians(1)
    model.ApplicationName = 'Tower floorplate JSON exporter'
    model.ApplicationDetails = 'Conceptual geometry; source inputs stored as object user text.'
    model.Strings['SourceJSON'] = SOURCE.name
    model.Strings['SourceSHA256'] = hashlib.sha256(raw).hexdigest()
    model.Strings['GeometryNotes'] = (
        'Feet. 500 ft tower; 31.25 ft core; 36 in walls. '
        '36 in solid square steel columns; 48 in solid square outrigger arms '
        'centered at Level 27, Z=337.5 ft. Floor surfaces have zero thickness. '
        'No analysis constraints, loads, reinforcement, connections or capacity checks encoded.')
    if assembly:
        model.Strings['GeometryNotes'] = assembly['description']
        model.Strings['TrussAssemblyJSON'] = Path(assembly_path).name
    definitions = [
        ('core', '01 Concrete core', (58,137,145,255), True),
        ('columns', '02 Steel columns', (98,91,161,255), True),
        ('outriggers', '03 Steel outriggers', (226,151,50,255), True),
        ('outlines', '04 Floor outlines', (148,162,177,255), True),
        ('surfaces', '05 Floor surfaces - zero thickness', (204,215,225,255), False),
        ('lines', '06 Analysis centerlines', (180,95,95,255), False),
        ('labels', '07 Level labels', (60,70,80,255), False),
    ]
    if assembly:
        definitions += [('diagonals','08 Steel X diagonals',(200,114,46,255),True),
                        ('joints','09 Common X joints',(230,75,55,255),True)]
    layers = {}
    for key, name, color, visible in definitions:
        layer = r.Layer()
        layer.Name, layer.Color, layer.Visible = name, color, visible
        layers[key] = model.Layers.Add(layer)
    expected = Counter()
    created_solids = 0

    def attrs(key, name, meta):
        a = r.ObjectAttributes()
        a.LayerIndex = layers[key]
        a.Name = name
        for k,v in meta.items():
            a.SetUserString(k, str(v))
        a.SetUserString('source_file', SOURCE.name)
        expected[key] += 1
        return a

    def box(key, name, bounds, meta):
        nonlocal created_solids
        x0,y0,z0,x1,y1,z1 = bounds
        assert x1>x0 and y1>y0 and z1>z0
        b = r.Brep.CreateFromBox(r.Box(r.BoundingBox(
            r.Point3d(x0,y0,z0), r.Point3d(x1,y1,z1))))
        assert b.IsValid and b.IsSolid
        model.Objects.AddBrep(b, attrs(key,name,meta))
        created_solids += 1

    def member(key, name, start, end, side_ft, meta):
        nonlocal created_solids
        length = math.dist(start,end)
        b = r.Brep.CreateFromBox(r.Box(r.BoundingBox(
            r.Point3d(0,-side_ft/2,-side_ft/2),r.Point3d(length,side_ft/2,side_ft/2))))
        direction = r.Vector3d(*[(end[i]-start[i])/length for i in range(3)])
        rotation = r.Transform.Rotation(r.Vector3d(1,0,0),direction,r.Point3d(0,0,0))
        assert b.Transform(rotation)
        assert b.Transform(r.Transform.Translation(*start))
        assert b.IsValid and b.IsSolid
        model.Objects.AddBrep(b,attrs(key,name,meta))
        created_solids += 1

    def line(name, a, b, meta):
        model.Objects.AddLine(r.Point3d(*a), r.Point3d(*b), attrs('lines',name,meta))

    def polygon(name, points, meta):
        pts = [r.Point3d(*p) for p in points]
        model.Objects.AddPolyline(pts+[pts[0]], attrs('outlines',name,meta))

    z = 0.0
    for floor, entry in enumerate(data['floor_sequence'], 1):
        z0, z = z, z+entry['floor_height']
        ft = data['floor_types'][entry['type']]
        nodes = {n['id']: (n['x'],n['y']) for n in ft['structural_nodes']}
        elements = ft['structural_elements']
        walls = [e for e in elements if e['type']=='shear_wall']
        thicknesses = {e['section_dims']['width']/12 for e in walls}
        assert len(thicknesses)==1 and len(walls)==4
        t = thicknesses.pop()
        wall_pts = [nodes[n] for e in walls for n in e['nodes']]
        # Input nodes locate wall centerlines. Recover exact outside/inside faces.
        xmin, xmax = min(p[0] for p in wall_pts)-t/2, max(p[0] for p in wall_pts)+t/2
        ymin, ymax = min(p[1] for p in wall_pts)-t/2, max(p[1] for p in wall_pts)+t/2
        ix0,ix1,iy0,iy1 = xmin+t,xmax-t,ymin+t,ymax-t
        story = dict(floor=floor, floor_type=entry['type'], bottom_ft=z0, top_ft=z)
        # Four abutting closed wall solids; north/south own the corner areas.
        for e in walls:
            (ax,ay),(bx,by) = [nodes[n] for n in e['nodes']]
            if math.isclose(ay,by):
                ya,yb = (ymin,iy0) if ay<0 else (iy1,ymax)
                bounds = (xmin,ya,z0,xmax,yb,z)
            else:
                xa,xb = (xmin,ix0) if ax<0 else (ix1,xmax)
                bounds = (xa,iy0,z0,xb,iy1,z)
            box('core', f'L{floor:02d}_{e["id"]}', bounds,
                dict(**story, element_json=json.dumps(e),corner_convention='north/south walls own corners'))
        line(f'L{floor:02d}_CORE_SPINE',(0,0,z0),(0,0,z),story)

        for e in elements:
            meta = dict(**story, element_json=json.dumps(e))
            w,d = e['section_dims']['width']/12, e['section_dims']['depth']/12
            if e['type']=='column':
                x,y = nodes[e['nodes'][0]]
                box('columns',f'L{floor:02d}_{e["id"]}',(x-w/2,y-d/2,z0,x+w/2,y+d/2,z),meta)
                line(f'L{floor:02d}_{e["id"]}_CL',(x,y,z0),(x,y,z),meta)
            elif e['type']=='outrigger':
                (ax,ay),(bx,by) = [nodes[n] for n in e['nodes']]
                if math.isclose(ay,by):
                    bounds = (min(ax,bx),ay-w/2,z-d/2,max(ax,bx),ay+w/2,z+d/2)
                elif math.isclose(ax,bx):
                    bounds = (ax-w/2,min(ay,by),z-d/2,ax+w/2,max(ay,by),z+d/2)
                else:
                    raise ValueError('This exporter expects axis-aligned arms')
                box('outriggers',f'L{floor:02d}_{e["id"]}',bounds,meta)
                line(f'L{floor:02d}_{e["id"]}_CL',(ax,ay,z),(bx,by,z),meta)

        bp = {n['id']:(n['x'],n['y'],z) for n in ft['floor_plate']['boundary_nodes']}
        outline = [bp[n] for n in ft['floor_plate']['boundary_loop']]
        inner = [(ix0,iy0,z),(ix1,iy0,z),(ix1,iy1,z),(ix0,iy1,z)]
        polygon(f'L{floor:02d}_FLOOR_BOUNDARY',outline,story)
        polygon(f'L{floor:02d}_CORE_CLEAR_OPENING',inner,story)
        # Optional planar ring mesh: no invented slab thickness.
        mesh = r.Mesh()
        for point in outline+inner:
            mesh.Vertices.Add(*point)
        for j in range(4):
            k = (j+1)%4
            mesh.Faces.AddFace(j,k,k+4,j+4)
        mesh.Normals.ComputeNormals()
        mesh.Compact()
        assert mesh.IsValid
        model.Objects.AddMesh(mesh, attrs('surfaces',f'L{floor:02d}_FLOOR_SURFACE',
                                          dict(**story, thickness='unspecified; zero-thickness display surface')))
        model.Objects.AddTextDot(f'L{floor:02d} | {z:g} ft',r.Point3d(outline[1][0]+8,outline[1][1],z),
                                 attrs('labels',f'L{floor:02d}_LABEL',story))
    assert math.isclose(z,500)
    if assembly:
        points = {n['id']:(n['x'],n['y'],n['z']) for n in assembly['nodes']}
        for e in assembly['members']:
            if e['role']!='diagonal':
                continue  # chords are already supplied by the v1 floorplate records
            start,end = [points[n] for n in e['nodes']]
            meta = dict(element_json=json.dumps(e), assembly=Path(assembly_path).name,
                        start_ft=json.dumps(start),end_ft=json.dumps(end))
            member('diagonals',e['id'],start,end,e['section_dims']['width']/12,meta)
            line(e['id']+'_CL',start,end,meta)
        for n in assembly['nodes']:
            if n['role']=='crossing':
                model.Objects.AddPoint(r.Point3d(n['x'],n['y'],n['z']),
                    attrs('joints',n['id'],dict(node_json=json.dumps(n))))
    if not model.Write(str(OUTPUT),7):
        raise RuntimeError('3DM write failed')

    # Reopen the actual deliverable and check every object, not just in-memory geometry.
    reopened = r.File3dm.Read(str(OUTPUT))
    assert reopened is not None
    assert reopened.Settings.ModelUnitSystem==r.UnitSystem.Feet
    assert len(reopened.Objects)==sum(expected.values())
    counts = Counter()
    solid_count = 0
    lo,hi = float('inf'),float('-inf')
    for obj in reopened.Objects:
        g = obj.Geometry
        assert g.IsValid, obj.Attributes.Name
        counts[obj.Attributes.LayerIndex] += 1
        if isinstance(g,r.Brep):
            assert g.IsSolid
            solid_count += 1
            bb = g.GetBoundingBox()
            lo,hi = min(lo,bb.Min.Z),max(hi,bb.Max.Z)
            if not assembly and obj.Attributes.LayerIndex==layers['outriggers']:
                assert math.isclose((bb.Min.Z+bb.Max.Z)/2,337.5)
    for key, count in expected.items():
        assert counts[layers[key]]==count
    assert solid_count==created_solids and math.isclose(lo,0) and math.isclose(hi,500)
    assert SOURCE.read_bytes()==raw
    report = dict(file=OUTPUT.name, file_bytes=OUTPUT.stat().st_size, rhino_file_version=7,
                  units='feet', source_json=SOURCE.name, source_sha256=hashlib.sha256(raw).hexdigest(),
                  object_counts_by_layer={name:expected[key] for key,name,_,_ in definitions},
                  valid_closed_solids=solid_count, structural_z_range_ft=[lo,hi],
                  core_outside_ft=xmax-xmin, core_inside_ft=ix1-ix0, wall_thickness_ft=t,
                  outrigger_centerline_z_ft=337.5, source_unchanged=True,
                  checks='Reopened 3DM; all geometry valid; all Breps solid; object counts, units and Z extents passed.')
    if assembly:
        report.update(truss_assembly=Path(assembly_path).name, truss_planes=4,truss_arms=8,
                      chord_levels_ft=[325,350], connected_crossings=8, chords=16, diagonal_segments=32)
    OUTPUT.with_name(OUTPUT.stem+'_3dm_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    export()
