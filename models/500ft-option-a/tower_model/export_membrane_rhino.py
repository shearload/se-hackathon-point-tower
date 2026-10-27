"""Export the final Option A solids plus the actual coarse analytical grid."""
from pathlib import Path
import json
import math
import rhino3dm as r
from export_rhino import export

ROOT=Path(__file__).resolve().parent.parent


def main():
    data=json.loads((ROOT/'tower_model/results_membrane/option_a/mesh_20ft/summary.json').read_text())
    inputs=data['floor_mesh_inputs']
    base=ROOT/'tower_500ft_option_a.3dm'
    if not base.exists():
        export(ROOT/inputs['floorplate_file'],base,ROOT/inputs['truss_assembly_file'])
    model=r.File3dm.Read(str(base))
    assert model is not None
    # Replace the earlier four-quad floor rings with the actual analysis cells.
    generic=[o.Attributes.Id for o in model.Objects if o.Attributes.Name.endswith('_FLOOR_SURFACE')]
    for guid in generic:
        model.Objects.Delete(guid)  # rhino3dm Delete returns None on success
    assert not any(o.Attributes.Name.endswith('_FLOOR_SURFACE') for o in model.Objects)
    layer=r.Layer()
    layer.Name='10 Coarse analytical floor mesh - toggle visibility'
    layer.Color=(165,185,201,255)
    layer.Visible=False
    index=model.Layers.Add(layer)
    coords=data['mesh']['mesh_coordinates_ft']
    inner=data['config']['core_ft']/2-data['config']['wall_in']/12
    cells=[]
    for i,(x0,x1) in enumerate(zip(coords[:-1],coords[1:])):
        for j,(y0,y1) in enumerate(zip(coords[:-1],coords[1:])):
            if abs((x0+x1)/2)<inner-1e-7 and abs((y0+y1)/2)<inner-1e-7:
                continue
            cells.append([(i,j),(i+1,j),(i+1,j+1),(i,j+1)])
    vertices=sorted({p for cell in cells for p in cell})
    vertex_ids={p:i for i,p in enumerate(vertices)}
    assert len(cells)==data['mesh']['floor_elements']
    assert len(vertices)==data['mesh']['floor_nodes']
    for floor in range(1,data['config']['stories']+1):
        mesh=r.Mesh()
        z=floor*data['config']['height_ft']/data['config']['stories']
        for i,j in vertices:
            mesh.Vertices.Add(coords[i],coords[j],z)
        for cell in cells:
            mesh.Faces.AddFace(*[vertex_ids[p] for p in cell])
        mesh.Normals.ComputeNormals()
        mesh.Compact()
        assert mesh.IsValid
        a=r.ObjectAttributes()
        a.LayerIndex=index
        a.Name=f'L{floor:02d}_ANALYTICAL_MEMBRANE_GRID'
        a.SetUserString('floor',str(floor))
        a.SetUserString('analysis_thickness_in','8')
        a.SetUserString('in_plane_stiffness_factor','0.7')
        a.SetUserString('slab_fc_ksi','6')
        a.SetUserString('behavior','in-plane analytical midsurface; no slab bending')
        model.Objects.AddMesh(mesh,a)
    model.Strings['AnalysisInputFile']='tower_floor_mesh_option_a_inputs.json'
    model.Strings['AnalysisMeshStatus']='Coarse mesh only; finer mesh stopped at user request; no convergence claim.'
    model.Strings['ColumnLayout']='Option A: 28 columns; 8 outrigger columns; central 28.25 ft c/c bay (25.25 ft clear between 36 in columns).'
    target=ROOT/'tower_500ft_option_a_membrane.3dm'
    assert model.Write(str(target),7)
    actual=r.File3dm.Read(str(target))
    solids=sum(isinstance(o.Geometry,r.Brep) and o.Geometry.IsSolid for o in actual.Objects)
    meshes=[o for o in actual.Objects if o.Attributes.Name.endswith('_ANALYTICAL_MEMBRANE_GRID')]
    assert solids==1328 and len(meshes)==40
    assert all(o.Geometry.IsValid for o in actual.Objects)
    assert sum(len(o.Geometry.Faces) for o in meshes)==data['mesh']['total_elements']
    report=dict(file=target.name,units='feet',valid_closed_solids=solids,
        analytical_floor_meshes=40,analytical_elements=data['mesh']['total_elements'],
        elements_per_floor=len(cells),nodes_per_floor=len(vertices),
        column_count=28,outrigger_columns=8,central_bay_center_to_center_ft=28.25,
        clear_between_column_faces_ft=25.25,mesh_layer_initially_hidden=True,
        mesh_layer=layer.Name,geometry_validity='Reopened 3DM; all geometry valid, all structural Breps closed.',
        refinement_status='not run; stopped by user')
    target.with_name(target.stem+'_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
