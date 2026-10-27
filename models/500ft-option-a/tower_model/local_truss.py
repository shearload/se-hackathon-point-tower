"""One-way, displacement-driven local outrigger assessment agreed with user.

Run tower_trussed.py first to export global interface movements, then this file.
The global model and Rhino geometry are not modified by this assessment.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
from collections import Counter
import openseespy.opensees as ops

ROOT=Path(__file__).resolve().parent.parent
GLOBAL=ROOT/'tower_model/results_trussed/summary.json'
ASSEMBLY=ROOT/'tower_500ft_truss_assembly.json'
OUTPUT=ROOT/'tower_model/results_local_truss'


def solve_arm(arm,assembly,movement,case,prescribe_column_horizontal=False):
    ops.wipe()
    ops.model('basic','-ndm',2,'-ndf',2)
    nodes=[n for n in assembly['nodes'] if n['arm_id']==arm['id']]
    members=[m for m in assembly['members'] if m['arm_id']==arm['id']]
    tags={n['id']:i+1 for i,n in enumerate(nodes)}
    horizontal=0 if arm['axis']=='X' else 1
    for n in nodes:
        ops.node(tags[n['id']],n['x' if arm['axis']=='X' else 'y']*12,n['z']*12)
    # Root translations in the truss plane are prescribed. Column connection
    # vertical movements are prescribed; horizontal movements remain free.
    # A 2D model inherently supplies the approved out-of-plane restraint.
    ops.timeSeries('Linear',1)
    ops.pattern('Plain',1,1)
    prescribed={}
    for n in nodes:
        tag=tags[n['id']]
        if n['role']=='wall_attachment':
            prescribed[(tag,1)]=movement[n['id']][horizontal]
            prescribed[(tag,2)]=movement[n['id']][2]
        elif n['role']=='column_attachment':
            prescribed[(tag,2)]=movement[n['id']][2]
            if prescribe_column_horizontal:
                prescribed[(tag,1)]=movement[n['id']][horizontal]
    for (tag,dof),value in prescribed.items():
        ops.sp(tag,dof,value)

    loads={tag:[0.0,0.0] for tag in tags.values()}
    properties=[]
    for i,m in enumerate(members,1):
        E=m['E']/1000
        area=m['section_dims']['width']*m['section_dims']['depth']
        ops.uniaxialMaterial('Elastic',i,E)
        ni,nj=[tags[n] for n in m['nodes']]
        ops.element('truss',i,ni,nj,area,i)
        length=math.dist(ops.nodeCoord(ni),ops.nodeCoord(nj))
        weight=length*area*0.490/1728
        loads[ni][1]-=weight/2
        loads[nj][1]-=weight/2
        properties.append((m,i,length,area,E))
    for tag,force in loads.items():
        ops.load(tag,*force)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.algorithm('Linear')
    ops.integrator('LoadControl',1.0)
    ops.analysis('Static')
    if ops.analyze(1)!=0:
        raise RuntimeError(f'Local model failed: {case} {arm["id"]}')
    ops.reactions()
    for (tag,dof),value in prescribed.items():
        assert math.isclose(ops.nodeDisp(tag,dof),value,rel_tol=1e-8,abs_tol=1e-8)
    force_scale=max(1.0,sum(abs(ops.nodeReaction(tag,d)) for tag in tags.values() for d in (1,2)))
    for direction in (1,2):
        residual=sum(ops.nodeReaction(tag,direction)+loads[tag][direction-1] for tag in tags.values())
        assert abs(residual)<1e-7*force_scale
    moment=sum(ops.nodeCoord(tag)[0]*(ops.nodeReaction(tag,2)+loads[tag][1])-
               ops.nodeCoord(tag)[1]*(ops.nodeReaction(tag,1)+loads[tag][0]) for tag in tags.values())
    assert abs(moment)<1e-7*force_scale*max(ops.nodeCoord(t)[1] for t in tags.values())
    # Free column horizontal equilibrium must be supplied by chords and braces,
    # not an imposed horizontal reaction from a floor diaphragm.
    for n in nodes:
        if n['role']=='column_attachment' and not prescribe_column_horizontal:
            assert abs(ops.nodeReaction(tags[n['id']],1))<1e-7*force_scale
    rows=[]
    energy=0.0
    for m,tag,length,area,E in properties:
        P=ops.eleResponse(tag,'axialForce')[0]
        stress=P/area
        energy+=P*P*length/(2*E*area)
        rows.append(dict(case=case,arm=arm['id'],member=m['id'],role=m['role'],
            section_side_in=m['section_dims']['width'],length_ft=length/12,
            axial_force_kip=P,axial_stress_ksi=stress,Fy_ksi=m['Fy']/1000,
            abs_stress_over_Fy=abs(stress)/(m['Fy']/1000)))
    work=sum((ops.nodeReaction(tag,d)+loads[tag][d-1])*ops.nodeDisp(tag,d)
             for tag in tags.values() for d in (1,2))
    assert math.isclose(work,2*energy,rel_tol=1e-6,abs_tol=1e-5)
    nodal=[dict(case=case,arm=arm['id'],node=n['id'],role=n['role'],
            horizontal_displacement_in=ops.nodeDisp(tags[n['id']],1),
            vertical_displacement_in=ops.nodeDisp(tags[n['id']],2),
            horizontal_reaction_kip=ops.nodeReaction(tags[n['id']],1),
            vertical_reaction_kip=ops.nodeReaction(tags[n['id']],2)) for n in nodes]
    return rows,nodal


def main():
    global_raw=GLOBAL.read_bytes()
    assembly_raw=ASSEMBLY.read_bytes()
    geometry=ROOT/'tower_500ft_trussed.3dm'
    geometry_hash=hashlib.sha256(geometry.read_bytes()).hexdigest()
    global_results=json.loads(global_raw)['results']
    assembly=json.loads(assembly_raw)
    on=[r for r in global_results if r['case'].startswith('outriggers')]
    snapshots={r['case'][-1]:r['assembly_node_displacements_in'] for r in on}
    gravity=snapshots['X']['gravity']
    for name in gravity:
        assert all(math.isclose(a,b,abs_tol=1e-8) for a,b in zip(gravity[name],snapshots['Y']['gravity'][name]))
    cases={'G':gravity}
    for axis in ('X','Y'):
        total=snapshots[axis]['gravity_plus_lateral']
        cases[f'G+{axis}']=total
        # Exact negative-direction solution by superposition in the unchanged
        # linear elastic global model; this is not a new design combination.
        cases[f'G-{axis}']={n:[2*g-t for g,t in zip(gravity[n],total[n])] for n in gravity}
    rows=[]
    nodes=[]
    for case,movement in cases.items():
        for arm in assembly['arms']:
            member_rows,node_rows=solve_arm(arm,assembly,movement,case)
            rows.extend(member_rows)
            nodes.extend(node_rows)
    assert len(rows)==240 and len(nodes)==200
    # X/Y symmetry is checked after enveloping both signs and all eight arms.
    for role in ('top_chord','bottom_chord','diagonal'):
        x=max(abs(r['axial_force_kip']) for r in rows if r['role']==role and r['case'] in ('G+X','G-X'))
        y=max(abs(r['axial_force_kip']) for r in rows if r['role']==role and r['case'] in ('G+Y','G-Y'))
        assert math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-5)
    assert max(abs(r['axial_force_kip']) for r in rows if r['role']=='top_chord')>1.0
    assert max(abs(r['axial_force_kip']) for r in rows if r['role']=='bottom_chord')>1.0
    envelope=[]
    for member in assembly['members']:
        records=[r for r in rows if r['member']==member['id']]
        tension=max(records,key=lambda r:r['axial_force_kip'])
        compression=min(records,key=lambda r:r['axial_force_kip'])
        peak=max(records,key=lambda r:abs(r['axial_force_kip']))
        envelope.append(dict(member=member['id'],role=member['role'],section_side_in=peak['section_side_in'],
            tension_kip=max(0,tension['axial_force_kip']),tension_case=tension['case'],
            compression_kip=max(0,-compression['axial_force_kip']),compression_case=compression['case'],
            peak_abs_stress_ksi=abs(peak['axial_stress_ksi']),peak_case=peak['case'],
            abs_stress_over_Fy=peak['abs_stress_over_Fy']))
    OUTPUT.mkdir(exist_ok=True)
    for name,records in [('member_results.csv',rows),('node_results.csv',nodes),('member_envelopes.csv',envelope)]:
        with (OUTPUT/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    peaks={role:max((e for e in envelope if e['role']==role),key=lambda e:e['peak_abs_stress_ksi'])
           for role in ('top_chord','bottom_chord','diagonal')}
    summary=dict(method='One-way displacement-driven local axial truss; pinned core translations prescribed; column horizontal translations free',
        source_global_results=str(GLOBAL.relative_to(ROOT)),global_results_sha256=hashlib.sha256(global_raw).hexdigest(),
        truss_assembly_sha256=hashlib.sha256(assembly_raw).hexdigest(),rhino_unchanged_sha256=geometry_hash,
        load_cases=list(cases),local_models_solved=40,member_records=240,
        global_model_feedback=False,geometry_changed=False,
        gravity='Half-lumped self-weight of the same six truss segments per arm; no separate column/floor loads added locally',
        peaks=peaks,member_envelopes=envelope,
        checks='Prescribed movement compatibility, force/moment equilibrium, free-column horizontal equilibrium, strain energy/work, X/Y envelopes, nonzero chord demands',
        limitations='Preliminary elastic demands for G and G +/- illustrative 1000-kip lateral probe. Not a code load envelope, capacity ratio, buckling/connection check or final sizing. Local forces are not fed back into the global model.')
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    write_report(summary)
    assert GLOBAL.read_bytes()==global_raw and ASSEMBLY.read_bytes()==assembly_raw
    assert hashlib.sha256(geometry.read_bytes()).hexdigest()==geometry_hash
    for role,peak in peaks.items():
        print(f"{role}: {peak['peak_abs_stress_ksi']:.3f} ksi, {peak['member']} ({peak['peak_case']})")
    print('40 local models solved; compatibility, equilibrium, energy, symmetry and nonzero chord-force checks passed.')


def write_report(s):
    lines=['# Local outrigger truss demand assessment','',
        'The global rigid-diaphragm model and Rhino geometry are retained. This separate',
        'local assessment follows the user-confirmed pinned, displacement-driven method.','',
        '| Member group | Placeholder section | Peak absolute axial force | Peak absolute axial stress | Governing case |',
        '| --- | --- | ---: | ---: | --- |']
    for role,p in s['peaks'].items():
        lines.append(f"| {role.replace('_',' ')} | {p['section_side_in']} in solid square | {max(p['tension_kip'],p['compression_kip']):.1f} kip | {p['peak_abs_stress_ksi']:.3f} ksi | {p['peak_case']} |")
    lines += ['', 'All steel has Fy = 50 ksi. Stress/Fy in the CSV is only a stress comparison,',
        '**not a design utilization or compression capacity check**. Member sizes remain placeholders.','',
        '## Boundary and load transfer','',
        'Each of the eight arms is modeled separately as a 2D, five-node elastic axial truss:',
        'two chords and four diagonal segments sharing one central joint. Global root',
        'horizontal and vertical translations are prescribed at both core connections.',
        'Global vertical translations are prescribed at both column connections; their',
        'horizontal translations are free. The column is outside the local cut boundary:',
        'its global behavior enters through the imposed end movements and is not duplicated.',
        'There are no rotational DOFs or moment connections. The 2D idealization represents',
        'the agreed restraint normal to each truss plane. Central in-plane motions are solved.','',
        'Self-weight is half-lumped at member ends, matching the global truss elements.',
        'No additional floor or column gravity loads are applied locally. Root and column',
        'joint gravity loads act on prescribed vertical DOFs; central joint gravity is',
        'explicitly applied. Actual support movements are included with their original',
        'signs and reference, rather than assuming fixed zero-vertical-displacement anchors.','',
        'Cases are G (D + L in the global model), G+X, G-X, G+Y and G-Y. Lateral cases',
        'use the original illustrative 1,000 kip triangular probe. Negative-direction',
        'global movements are obtained by exact linear superposition: 2u_G - u_(G+axis).',
        'They are demand cases for this probe, not factored code combinations.','',
        '## Verification and interpretation','',
        'All 40 local solves passed displacement compatibility, horizontal/vertical force',
        'equilibrium, moment equilibrium, zero free-column horizontal reaction, strain',
        'energy versus external work and X/Y envelope symmetry checks. Both chord groups',
        'now have nonzero demands. Source global result and Rhino hashes are recorded in',
        '`results_local_truss/summary.json` and verified unchanged by the local run.','',
        'This one-way assessment removes the diaphragm bypass locally, but its redistributed',
        'forces are not fed back into the global model. It is not a coupled solution of',
        'the tower and modified trusses, nor an established conservative bound. Local',
        'core anchorage, column forces, out-of-plane restraint and diaphragm design need',
        'a coordinated design model. No buckling length, connection stiffness, design',
        'load combinations, material nonlinearity or final section optimization is assumed.','',
        '## Files and rerun','',
        '- `results_local_truss/member_results.csv`: all 240 signed member demands.',
        '- `results_local_truss/member_envelopes.csv`: 48 member tension/compression envelopes.',
        '- `results_local_truss/node_results.csv`: imposed/solved movements and reactions.',
        '- `results_local_truss/summary.json`: source hashes, peaks and method metadata.','',
        '```powershell','python tower_model/tower_trussed.py','python tower_model/local_truss.py','```','']
    (ROOT/'tower_model/LOCAL_TRUSS_ASSESSMENT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
