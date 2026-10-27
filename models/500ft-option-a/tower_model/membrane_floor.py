"""Finite in-plane floors, with local rigid core cross-sections only."""
from collections import defaultdict
import math
import openseespy.opensees as ops


def make_floor_builder(inputs,spacing_ft):
    def build(c,columns,core,col):
        half=c.plan_ft*6
        face=c.core_ft*6
        inner=face-c.wall_in
        cl=face-c.wall_in/2
        crossing=(half+face)/2
        anchors=sorted(set([-half,-crossing,-face,-cl,-inner,0,inner,cl,face,crossing,half]+
                           [coordinate for p in columns for coordinate in p]))
        coordinates=[]
        for a,b in zip(anchors[:-1],anchors[1:]):
            divisions=math.ceil((b-a)/(spacing_ft*12)-1e-10)
            coordinates += [a+(b-a)*i/divisions for i in range(divisions)]
        coordinates.append(anchors[-1])
        cells=[]
        for i,(x0,x1) in enumerate(zip(coordinates[:-1],coordinates[1:])):
            for j,(y0,y1) in enumerate(zip(coordinates[:-1],coordinates[1:])):
                if abs((x0+x1)/2)<inner-1e-7 and abs((y0+y1)/2)<inner-1e-7:
                    continue
                cells.append(([(i,j),(i+1,j),(i+1,j+1),(i,j+1)],(x1-x0)*(y1-y0)))
        active=sorted({p for points,_ in cells for p in points})
        tributary=defaultdict(float)
        for points,area in cells:
            for p in points:
                tributary[p]+=area/4
        area=sum(area for _,area in cells)
        expected=(2*half)**2-(2*inner)**2
        assert math.isclose(area,expected,rel_tol=1e-12)
        Ec=57000*math.sqrt(inputs['slab_fc_ksi']*1000)/1000
        effective_E=Ec*inputs['in_plane_stiffness_factor']
        ops.section('ElasticMembranePlateSection',100,effective_E,
                    inputs['slab_poisson_ratio'],inputs['slab_thickness_in'],0,0)
        lookup={}
        floor_areas={}
        element=100000
        for k in range(1,c.stories+1):
            local_tags={p:100000+k*10000+i for i,p in enumerate(active)}
            core_boundary=[]
            for (i,j),tag in local_tags.items():
                x,y=coordinates[i],coordinates[j]
                ops.node(tag,x,y,k*c.height_ft*12/c.stories)
                # This membrane has no vertical gravity/bending participation.
                ops.fix(tag,0,0,1,1,1,0)
                lookup[(k,round(x,7),round(y,7))]=tag
                if abs(x)<=face+1e-7 and abs(y)<=face+1e-7:
                    core_boundary.append(tag)
            # Rigid ties are confined to the core's wall footprint, not the
            # floor plate: this is the retained box-spine cross-section model.
            ops.rigidDiaphragm(3,core(k),*core_boundary)
            for j,(x,y) in enumerate(columns):
                node=lookup[(k,round(x,7),round(y,7))]
                ops.equalDOF(col(k,j),node,1,2)
            for points,_ in cells:
                element+=1
                ops.element('ShellMITC4',element,*[local_tags[p] for p in points],100)
            floor_areas[k]={local_tags[p]:a for p,a in tributary.items()}
        return dict(lookup=lookup,tributaries=floor_areas,area_in2=area,
            stats=dict(requested_max_spacing_ft=spacing_ft,
                actual_max_spacing_ft=max(b-a for a,b in zip(coordinates[:-1],coordinates[1:]))/12,
                floor_nodes=len(active),floor_elements=len(cells),
                total_nodes=len(active)*c.stories,total_elements=len(cells)*c.stories,
                floor_area_ft2=area/144,Ec_gross_ksi=Ec,E_effective_ksi=effective_E,
                slab_thickness_in=inputs['slab_thickness_in'],bending_modifier=0,
                mesh_coordinates_ft=[x/12 for x in coordinates],
                mass_distribution='all existing floor-level weight distributed by nodal tributary area; no duplicate element mass',
                shell_density=0,core_constraints='wall footprint only',column_constraints='UX/UY only'))
    return build
