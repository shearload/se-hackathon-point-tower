"""Conceptual 500-ft core/outrigger tower. Units: kip, inch, second.

Run: python tower.py   (writes results/ next to this file)
Elastic stiffness study only; see README.md before interpreting results.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import csv
import json
import math
import argparse


@dataclass
class Config:
    height_ft: float = 500.0
    stories: int = 40
    plan_ft: float = 220 + 11 / 12
    core_ft: float = 500.0 / 16.0  # user's height-to-core-width ratio
    wall_in: float = 36.0
    fc_ksi: float = 8.0
    fy_ksi: float = 50.0
    Es_ksi: float = 29000.0
    column_side_in: float = 36.0  # assumed SOLID squares, not HSS
    outrigger_side_in: float = 48.0  # assumed SOLID equivalent squares
    core_I_factor: float = 1.0  # gross baseline; user may vary for cracking
    core_G_factor: float = 1.0
    dead_psf: float = 150.0  # includes slab, finishes, partitions; excludes vertical members
    live_psf: float = 50.0
    mass_live_fraction: float = 0.25
    core_floor_gravity_fraction: float = 0.50
    lateral_base_shear_kip: float = 1000.0  # arbitrary stiffness probe, not a design load


def properties(c):
    b, t = c.core_ft * 12, c.wall_in
    if not (0 < 2*t < b and c.plan_ft > c.core_ft and c.stories > 2):
        raise ValueError('Invalid geometry')
    Ec = 57000 * math.sqrt(c.fc_ksi * 1000) / 1000  # assumed normal-weight Ec, ksi
    return dict(Ec_ksi=Ec, Gc_ksi=Ec/(2*1.2)*c.core_G_factor,
                A=b*b-(b-2*t)**2, I=(b**4-(b-2*t)**4)/12*c.core_I_factor,
                J=t*(b-t)**3, Av=2*t*(b-t),
                floor_area_ft2=c.plan_ft**2-(c.core_ft-2*t/12)**2)


def build(c, outriggers=True, coords_override=None, truss_assembly=None, floor_mesh=None):
    import openseespy.opensees as ops
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    p = properties(c)
    h, half = c.height_ft*12/c.stories, c.plan_ft*6
    # 16 columns: five equally spaced positions per side, corners counted once.
    coords = [(x*half/2, y*half/2) for x in range(-2, 3)
              for y in range(-2, 3) if abs(x) == 2 or abs(y) == 2]
    if coords_override is not None:
        coords = list(coords_override)
    core = lambda k: k+1
    col = lambda k, j: 1000 + k*100+j
    outrigger_level = round(2*c.stories/3)
    ops.geomTransf('Linear', 1, 1, 0, 0)  # vertical member local x = global Z
    ops.geomTransf('Linear', 2, 0, 0, 1)  # horizontal members
    tag = 0
    def beam(i, j, side, transf):
        nonlocal tag
        tag += 1
        ops.element('elasticBeamColumn', tag, i, j, side**2, c.Es_ksi,
                    c.Es_ksi/2.6, 0.1406*side**4, side**4/12, side**4/12, transf)
        return tag
    for k in range(c.stories+1):
        ops.node(core(k), 0, 0, k*h)
        for j, (x, y) in enumerate(coords):
            ops.node(col(k,j), x, y, k*h)
        if k == 0:
            for n in [core(k)] + [col(k,j) for j in range(len(coords))]:
                ops.fix(n, 1, 1, 1, 1, 1, 1)
        else:
            if floor_mesh is None:
                ops.rigidDiaphragm(3, core(k), *[col(k,j) for j in range(len(coords))])
            tag += 1
            ops.element('ElasticTimoshenkoBeam', tag, core(k-1), core(k),
                        p['Ec_ksi'], p['Gc_ksi'], p['A'], p['J'], p['I'], p['I'],
                        p['Av'], p['Av'], 1)
            for j in range(len(coords)):
                beam(col(k-1,j), col(k,j), c.column_side_in, 1)
    meshes = floor_mesh(c,coords,core,col) if floor_mesh else None
    arms = []
    analysis_nodes = {}
    arm_weight = 0.0
    member_weight_by_level = {}
    if outriggers and truss_assembly:
        ops.uniaxialMaterial('Elastic', 1, c.Es_ksi)
        for j,n in enumerate(truss_assembly['nodes']):
            k=round(n['z']*12/h)
            xyz=(n['x']*12,n['y']*12,n['z']*12)
            if n['role']=='column_attachment':
                column_index=coords.index(xyz[:2])
                analysis_nodes[n['id']]=col(k,column_index)
                continue
            nt=9000+j
            ops.node(nt,*xyz)
            analysis_nodes[n['id']]=nt
            if n['role']=='wall_attachment':
                ops.rigidLink('beam',core(k),nt)
            else:
                # Pin-jointed planar X crossing: constrain the zero-stiffness
                # normal translation and all unused rotational DOFs.
                if meshes:
                    mesh_tag=meshes['lookup'][(k,round(n['x']*12,7),round(n['y']*12,7))]
                    ops.equalDOF(mesh_tag,nt,2 if n['plane_axis']=='X' else 1)
                    ops.fix(nt,0,0,0,1,1,1)
                else:
                    ops.fix(nt,0 if n['plane_axis']=='X' else 1,
                             1 if n['plane_axis']=='X' else 0,0,1,1,1)
        node_info={n['id']:n for n in truss_assembly['nodes']}
        for member in truss_assembly['members']:
            tag+=1
            ni,nj=[analysis_nodes[n] for n in member['nodes']]
            area=member['section_dims']['width']*member['section_dims']['depth']
            ops.element('truss',tag,ni,nj,area,1)
            length=math.dist(ops.nodeCoord(ni),ops.nodeCoord(nj))
            w=length*area*0.490/1728
            arms.append((tag,ni,nj,w))
            for endpoint in member['nodes']:
                level=round(node_info[endpoint]['z']*12/h)
                member_weight_by_level[level]=member_weight_by_level.get(level,0)+w/2
    elif outriggers:
        for a, (dx, dy) in enumerate([(1,0),(-1,0),(0,1),(0,-1)]):
            n = 9000+a
            ops.node(n, dx*c.core_ft*6, dy*c.core_ft*6, outrigger_level*h)
            # Rigid core cross-section offset transfers bending rotation to arm root.
            # Each slave has one retained node; no nested MP constraints.
            ops.rigidLink('beam', core(outrigger_level), n)
            j = coords.index((dx*half, dy*half))
            e = beam(n, col(outrigger_level,j), c.outrigger_side_in, 2)
            w = ((c.plan_ft-c.core_ft)*6)*c.outrigger_side_in**2*0.490/1728
            arms.append((e,n,col(outrigger_level,j),w))
            arm_weight += w
    # All weight/mass explicitly lumped: do not also set element mass.
    # floor_area excludes the entire clear hollow core; no internal core slabs modeled.
    floor_D = p['floor_area_ft2']*c.dead_psf/1000
    floor_L = p['floor_area_ft2']*c.live_psf/1000
    wall_w = p['A']*h*0.150/1728
    col_w = c.column_side_in**2*h*0.490/1728
    gravity = {}
    mass_weight = 0.0
    for k in range(1,c.stories+1):
        # Tributary half-segments: base receives bottom half directly.
        seg = 0.5 if k == c.stories else 1.0
        gravity[core(k)] = (floor_D+floor_L)*c.core_floor_gravity_fraction + seg*wall_w
        for j in range(len(coords)):
            gravity[col(k,j)] = (floor_D+floor_L)*(1-c.core_floor_gravity_fraction)/len(coords)+seg*col_w
        w = floor_D+c.mass_live_fraction*floor_L+seg*(wall_w+len(coords)*col_w)
        if truss_assembly:
            w += member_weight_by_level.get(k,0)
        elif k == outrigger_level:
            w += arm_weight
        mass_weight += w
        m = w/386.089
        # Approximate centered uniform annular floor polar inertia; member mass uses same distribution.
        B, bi = c.plan_ft*12, (c.core_ft*12-2*c.wall_in)
        r2 = (B**4-bi**4)/(6*(B**2-bi**2))
        if meshes:
            for node,area in meshes['tributaries'][k].items():
                mn=m*area/meshes['area_in2']
                ops.mass(node,mn,mn,0,0,0,0)
        else:
            ops.mass(core(k), m, m, 0, 0, 0, m*r2)
    gravity[core(0)] = 0.5*wall_w
    for j in range(len(coords)):
        gravity[col(0,j)] = 0.5*col_w
    for _, n, tip, w in arms:
        gravity[n] = gravity.get(n,0)+w/2
        gravity[tip] = gravity.get(tip,0)+w/2
    return dict(core=core, col=col, coords=coords, h=h, arms=arms,
                level=outrigger_level, gravity=gravity, mass_weight=mass_weight,
                bases=[core(0)]+[col(0,j) for j in range(len(coords))], properties=p,
                truss_assembly=truss_assembly,assembly_node_tags=analysis_nodes,meshes=meshes)


def solve(c, with_outriggers, axis, output, builder=build, solver='BandGeneral', periods_override=None):
    import openseespy.opensees as ops
    m = builder(c, with_outriggers)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system(solver)
    ops.test('NormDispIncr', 1e-9, 15)
    ops.algorithm('Linear')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')
    if periods_override is None:
        eigen = ops.eigen('-genBandArpack', 6)
        if any(v <= 0 for v in eigen):
            raise RuntimeError('Nonpositive eigenvalue')
        periods = [2*math.pi/math.sqrt(v) for v in eigen]
    else:
        periods = list(periods_override)
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    for n,w in m['gravity'].items():
        ops.load(n, 0,0,-w,0,0,0)
    if ops.analyze(1) != 0:
        raise RuntimeError('Gravity analysis failed')
    ops.reactions()
    total_weight = sum(m['gravity'].values())
    if abs(sum(ops.nodeReaction(n,3) for n in m['bases'])-total_weight)>1e-5*total_weight:
        raise RuntimeError('Gravity equilibrium failed')
    gravity_disp = {k:ops.nodeDisp(m['core'](k),axis) for k in range(1,c.stories+1)}
    gravity_assembly_displacements={name:list(ops.nodeDisp(tag))
                                   for name,tag in m['assembly_node_tags'].items()}
    gravity_truss_forces={member['id']:ops.eleResponse(e,'axialForce')[0]
        for member,(e,_,_,_) in zip(m['truss_assembly']['members'],m['arms'])} if m.get('truss_assembly') else {}
    ops.loadConst('-time',0.0)
    ops.timeSeries('Linear',2)
    ops.pattern('Plain',2,2)
    sum_z = sum(k*m['h'] for k in range(1,c.stories+1))
    moment = 0.0
    for k in range(1,c.stories+1):
        f = c.lateral_base_shear_kip*k*m['h']/sum_z
        force = [0.0]*6
        force[axis-1] = f
        if m.get('meshes'):
            for node,area in m['meshes']['tributaries'][k].items():
                ops.load(node,*[v*area/m['meshes']['area_in2'] for v in force])
        else:
            ops.load(m['core'](k), *force)
        moment += f*k*m['h']
    if ops.analyze(1) != 0:
        raise RuntimeError('Lateral analysis failed')
    ops.reactions()
    shear = sum(ops.nodeReaction(n,axis) for n in m['bases'])
    if abs(shear+c.lateral_base_shear_kip)>1e-5*c.lateral_base_shear_kip:
        raise RuntimeError('Lateral equilibrium failed')
    # Include vertical-reaction couples, essential for outrigger action.
    overturn = sum(ops.nodeReaction(n,5 if axis==1 else 4) +
                   (-ops.nodeCoord(n)[0] if axis==1 else ops.nodeCoord(n)[1])*ops.nodeReaction(n,3)
                   for n in m['bases'])
    expected = -moment if axis==1 else moment
    if abs(overturn-expected)>1e-5*moment:
        raise RuntimeError('Overturning equilibrium failed')
    rows, previous = [], 0.0
    for k in range(1,c.stories+1):
        u = ops.nodeDisp(m['core'](k),axis)-gravity_disp[k]
        rows.append([k,k*m['h']/12,u,(u-previous)/m['h']])
        previous = u
    name = ('outriggers' if with_outriggers else 'no_outriggers')+('_X' if axis==1 else '_Y')
    with (output/(name+'.csv')).open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['floor','height_ft','lateral_displacement_in','story_drift_ratio'])
        writer.writerows(rows)
    with (output/(name+'_reactions.csv')).open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['node','x_in','y_in','Rx_kip','Ry_kip','Rz_kip','Mx_kip_in','My_kip_in','Mz_kip_in'])
        for n in m['bases']:
            writer.writerow([n,*ops.nodeCoord(n)[:2],*ops.nodeReaction(n)])
    arm_forces = {str(e):list(ops.eleResponse(e,'axialForce' if m.get('truss_assembly') else 'localForce'))
                  for e,_,_,_ in m['arms']}
    member_results=[]
    if m.get('truss_assembly'):
        for member,(e,_,_,_) in zip(m['truss_assembly']['members'],m['arms']):
            area=member['section_dims']['width']*member['section_dims']['depth']
            force=ops.eleResponse(e,'axialForce')[0]
            member_results.append(dict(id=member['id'],role=member['role'],
                axial_force_kip=force,axial_stress_ksi=force/area,Fy_ksi=member['Fy']/1000))
    mesh_stats=m['meshes']['stats'] if m.get('meshes') else None
    return dict(case=name, periods_s=periods, roof_displacement_in=rows[-1][2],
                max_story_drift_ratio=max(abs(r[3]) for r in rows),
                weight_D_plus_L_kip=total_weight, dynamic_weight_kip=m['mass_weight'],
                base_shear_reaction_kip=shear, base_overturning_kip_in=overturn,
                outrigger_level=m['level'],outrigger_height_ft=m['level']*m['h']/12,
                outrigger_local_end_forces=arm_forces, section_properties=m['properties'],
                truss_member_results=member_results,
                gravity_truss_forces_kip=gravity_truss_forces,mesh_stats=mesh_stats,
                assembly_node_displacements_in=dict(gravity=gravity_assembly_displacements,
                    gravity_plus_lateral={name:list(ops.nodeDisp(tag))
                        for name,tag in m['assembly_node_tags'].items()}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='JSON overrides of Config fields')
    args=parser.parse_args()
    c=Config(**(json.loads(args.config.read_text()) if args.config else {}))
    output=Path(__file__).resolve().parent/'results'
    output.mkdir(exist_ok=True)
    results=[solve(c,on,axis,output) for on in (False,True) for axis in (1,2)]
    # Symmetric geometry/loading should yield matching X/Y displacement.
    for a,b in [(results[0],results[1]),(results[2],results[3])]:
        if not math.isclose(a['roof_displacement_in'],b['roof_displacement_in'],rel_tol=1e-5):
            raise RuntimeError('X/Y symmetry check failed')
    for a,b in [(results[0],results[2]),(results[1],results[3])]:
        if not abs(b['roof_displacement_in']) < abs(a['roof_displacement_in']):
            raise RuntimeError('Outriggers did not improve lateral stiffness')
    (output/'summary.json').write_text(json.dumps(dict(config=asdict(c),results=results),indent=2))
    for r in results:
        print(f"{r['case']}: roof={r['roof_displacement_in']:.4f} in; T1={r['periods_s'][0]:.4f} s")


if __name__ == '__main__':
    main()
