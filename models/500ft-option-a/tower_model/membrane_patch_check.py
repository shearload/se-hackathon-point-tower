"""Element verification fixture, independent of tower design parameters."""
import json
from pathlib import Path
import openseespy.opensees as ops


def run():
    ops.wipe()
    ops.model('basic','-ndm',3,'-ndf',6)
    for tag,(x,y) in enumerate([(0,0),(120,0),(120,120),(0,120)],1):
        ops.node(tag,x,y,0)
        ops.fix(tag,0,0,1,1,1,0)
    # Ep_modifier=0 removes slab bending. UZ/RX/RY are excluded explicitly;
    # RZ stays free so the shell drilling stabilization admits rigid rotation.
    ops.section('ElasticMembranePlateSection',1,4000,0.2,8,0,0)
    ops.element('ShellMITC4',1,1,2,3,4,1)
    ops.timeSeries('Linear',1)
    ops.pattern('Plain',1,1)
    for tag in (1,4):
        ops.sp(tag,1,0)
    for tag in (2,3):
        ops.sp(tag,1,0.01)
    ops.sp(1,2,0)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('UmfPack')
    ops.algorithm('Linear')
    ops.integrator('LoadControl',1)
    ops.analysis('Static')
    assert ops.analyze(1)==0
    ops.reactions()
    force=sum(ops.nodeReaction(n,1) for n in (2,3))
    expected=4000*8*120*0.01/120
    assert abs(force-expected)<expected*1e-6
    assert abs(ops.nodeDisp(3,2)+0.2*0.01)<1e-7
    result=dict(element='ShellMITC4',membrane_only=True,solver='UmfPack',
        axial_patch_reaction_kip=force,expected_reaction_kip=expected,
        poisson_contraction_in=ops.nodeDisp(3,2),expected_contraction_in=-0.002)
    target=Path(__file__).resolve().parent/'membrane_patch_check.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return result


if __name__=='__main__':
    run()
