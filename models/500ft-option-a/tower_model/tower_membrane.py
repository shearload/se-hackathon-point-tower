"""Coupled tower / steel trusses / finite floor membranes; same-model cut checks."""
from pathlib import Path
from dataclasses import asdict
import argparse
import csv
import json
import math
import time
import hashlib
import tower
from membrane_floor import make_floor_builder
from local_truss import solve_arm

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spacing',type=float,default=20)
    parser.add_argument('--inputs',type=Path,default=ROOT/'tower_floor_mesh_option_a_inputs.json')
    args=parser.parse_args()
    input_raw=args.inputs.read_bytes()
    inputs=json.loads(input_raw)
    assembly=json.loads((ROOT/inputs['truss_assembly_file']).read_text())
    fp=json.loads((ROOT/inputs['floorplate_file']).read_text())
    ft=fp['floor_types']['A']
    wall=next(e for e in ft['structural_elements'] if e['type']=='shear_wall')
    steel=next(e for e in ft['structural_elements'] if e['type']=='column')
    wall_ids={n for e in ft['structural_elements'] if e['type']=='shear_wall' for n in e['nodes']}
    wall_x=[n['x'] for n in ft['structural_nodes'] if n['id'] in wall_ids]
    plan_x=[n['x'] for n in ft['floor_plate']['boundary_nodes']]
    c=tower.Config(height_ft=sum(f['floor_height'] for f in fp['floor_sequence']),
        stories=len(fp['floor_sequence']),plan_ft=max(plan_x)-min(plan_x),
        core_ft=max(wall_x)-min(wall_x)+wall['section_dims']['width']/12,
        wall_in=wall['section_dims']['width'],fc_ksi=wall['Fy']/1000,
        fy_ksi=steel['Fy']/1000,Es_ksi=steel['E']/1000,
        column_side_in=steel['section_dims']['width'],outrigger_side_in=36)
    c.dead_psf=inputs['floor_dead_psf_including_slab']
    c.live_psf=inputs['floor_live_psf']
    c.mass_live_fraction=inputs['mass_live_fraction']
    c.lateral_base_shear_kip=inputs['lateral_base_shear_kip']
    c.core_floor_gravity_fraction=inputs['core_floor_gravity_fraction']
    slab_self_weight=inputs['slab_thickness_in']/12*inputs['slab_density_pcf']
    assert c.dead_psf>=slab_self_weight
    column_ids={e['nodes'][0] for e in fp['floor_types']['A']['structural_elements'] if e['type']=='column'}
    coords=[(n['x']*12,n['y']*12) for n in fp['floor_types']['A']['structural_nodes'] if n['id'] in column_ids]
    floors=make_floor_builder(inputs,args.spacing)
    def builder(config,on):
        return tower.build(config,on,coords_override=coords,truss_assembly=assembly,floor_mesh=floors)
    revision='option_a' if len(coords)==28 else 'prior_layout'
    out=ROOT/f'tower_model/results_membrane/{revision}/mesh_{args.spacing:g}ft'
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    started=time.monotonic()
    for axis in (1,2):
        print(f'Mesh {args.spacing:g} ft, axis {axis}: building and solving global model...',flush=True)
        result=tower.solve(c,True,axis,out,builder=builder,solver='UmfPack',
                           periods_override=results[0]['periods_s'] if results else None)
        results.append(result)
        print(f"  roof={result['roof_displacement_in']:.5f} in; T1={result['periods_s'][0]:.5f} s; elapsed={time.monotonic()-started:.1f} s",flush=True)
    assert math.isclose(results[0]['roof_displacement_in'],results[1]['roof_displacement_in'],rel_tol=1e-5)
    # Independent total-weight check includes the new column count.
    p=tower.properties(c)
    global_weight=p['floor_area_ft2']*(c.dead_psf+c.live_psf)/1000*c.stories
    global_weight+=p['A']*c.height_ft*12*0.150/1728
    global_weight+=len(coords)*c.column_side_in**2*c.height_ft*12*0.490/1728
    node_positions={n['id']:(n['x'],n['y'],n['z']) for n in assembly['nodes']}
    global_weight+=sum(math.dist(*(node_positions[n] for n in e['nodes']))*12*
        e['section_dims']['width']*e['section_dims']['depth']*0.490/1728 for e in assembly['members'])
    assert all(math.isclose(r['weight_D_plus_L_kip'],global_weight,rel_tol=1e-12) for r in results)
    checks,envelopes,peaks=check_cuts(assembly,results,out)
    summary=dict(config=asdict(c),floor_mesh_inputs=inputs,results=results,
        slab_self_weight_psf=slab_self_weight,superimposed_dead_psf=c.dead_psf-slab_self_weight,
        mesh=results[0]['mesh_stats'],member_peaks=peaks,member_envelopes=envelopes,
        column_count=len(coords),geometry_revision=revision,inputs_sha256=hashlib.sha256(input_raw).hexdigest(),
        reconciliation=checks,elapsed_s=time.monotonic()-started,
        limitations='Elastic membrane-only diaphragm; rigid core cross-section; retained gravity split; illustrative 1000-kip lateral probe; no final sizing or capacity check')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Completed finite floor model and local/global cut verification.',flush=True)
    for role,peak in peaks.items():
        print(f"{role}: peak |stress|={peak['peak_abs_stress_ksi']:.5f} ksi ({peak['case']})",flush=True)


def check_cuts(assembly,results,out):
    snapshots={r['case'][-1]:r['assembly_node_displacements_in'] for r in results}
    gravity=snapshots['X']['gravity']
    gravity_force=results[0]['gravity_truss_forces_kip']
    cases={'G':(gravity,gravity_force)}
    for result in results:
        axis=result['case'][-1]
        total=snapshots[axis]['gravity_plus_lateral']
        forces={e['id']:e['axial_force_kip'] for e in result['truss_member_results']}
        cases[f'G+{axis}']=(total,forces)
        cases[f'G-{axis}']=({n:[2*g-t for g,t in zip(gravity[n],total[n])] for n in gravity},
                            {name:2*gravity_force[name]-value for name,value in forces.items()})
    rows=[]
    max_error=0.0
    max_relative=0.0
    for case,(movement,forces) in cases.items():
        for arm in assembly['arms']:
            # Dirichlet cut verification of this SAME global model, not the
            # earlier free-horizontal-column design assessment. Prescribing
            # all interface translations transfers the membrane compatibility.
            local_rows,_=solve_arm(arm,assembly,movement,case,prescribe_column_horizontal=True)
            for row in local_rows:
                reference=forces[row['member']]
                error=abs(row['axial_force_kip']-reference)
                scale=max(1,abs(reference))
                assert error<1e-4+1e-6*abs(reference),(row['member'],error,reference)
                max_error=max(max_error,error)
                max_relative=max(max_relative,error/scale)
                rows.append(dict(case=case,member=row['member'],role=row['role'],
                    global_force_kip=reference,cut_local_force_kip=row['axial_force_kip'],
                    difference_kip=row['axial_force_kip']-reference,
                    axial_stress_ksi=row['axial_stress_ksi']))
    assert len(rows)==240
    envelope=[]
    for member in assembly['members']:
        records=[r for r in rows if r['member']==member['id']]
        peak=max(records,key=lambda r:abs(r['axial_stress_ksi']))
        envelope.append(dict(member=member['id'],role=member['role'],case=peak['case'],
            tension_kip=max(0,max(r['global_force_kip'] for r in records)),
            compression_kip=max(0,-min(r['global_force_kip'] for r in records)),
            peak_abs_stress_ksi=abs(peak['axial_stress_ksi']),
            side_in=member['section_dims']['width']))
    peaks={role:max((e for e in envelope if e['role']==role),key=lambda e:e['peak_abs_stress_ksi'])
           for role in ('top_chord','bottom_chord','diagonal')}
    for name,data in [('local_global_cut_comparison.csv',rows),('member_envelopes.csv',envelope)]:
        with (out/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    return dict(local_models=40,member_comparisons=240,
        max_absolute_force_difference_kip=max_error,max_relative_error_normalized_by_max_1kip=max_relative,
        method='same-model cut with all wall/column in-plane translations prescribed from finite-membrane global model',
        checks='global equilibrium, X/Y roof symmetry, independently calculated gravity weight, local compatibility/equilibrium/energy, member force agreement'),envelope,peaks


if __name__=='__main__':
    main()
