"""Static review drawing from final Option A inputs and recorded coarse mesh."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent.parent
s=json.loads((ROOT/'tower_model/results_membrane/option_a/mesh_20ft/summary.json').read_text())
fp=json.loads((ROOT/'tower_floorplate_500ft_option_a.json').read_text())
a=json.loads((ROOT/'tower_500ft_option_a_truss_assembly.json').read_text())
im=Image.new('RGB',(1550,1120),'#f6f9fc')
d=ImageDraw.Draw(im)
def f(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
def text(x,y,v,size=22,bold=False,color='#21394e'):
    d.text((x,y),v,font=f(size,bold),fill=color)
text(38,27,'Final Option A: 28 columns with finite floor membranes',34,True)
text(38,79,'500 ft tower | 8 wall-end X-braced outrigger arms | 8 in slab, 6 ksi concrete, 70% in-plane stiffness',22)
half=s['config']['plan_ft']/2
scale=750/(2*half)
cx,cy=450,585
def p(x,y):
    return cx+x*scale,cy-y*scale
coords=s['mesh']['mesh_coordinates_ft']
inner=12.625
for i,(x0,x1) in enumerate(zip(coords[:-1],coords[1:])):
    for j,(y0,y1) in enumerate(zip(coords[:-1],coords[1:])):
        if abs((x0+x1)/2)<inner-1e-7 and abs((y0+y1)/2)<inner-1e-7:
            continue
        q0,q1=p(x0,y1),p(x1,y0)
        d.rectangle((*q0,*q1),fill='#edf3f7',outline='#b0c3d1',width=1)
q0,q1=p(-15.625,15.625),p(15.625,-15.625)
d.rectangle((*q0,*q1),fill='#70a9ad',outline='#287783',width=2)
q0,q1=p(-inner,inner),p(inner,-inner)
d.rectangle((*q0,*q1),fill='white',outline='#287783',width=2)
for arm in a['arms']:
    d.line([p(*arm['core_face_xy_ft']),p(*arm['column_xy_ft'])],fill='#ce852a',width=4)
nodes={n['id']:n for n in fp['floor_types']['A']['structural_nodes']}
outrigger_ids={arm['column_node_id'] for arm in a['arms']}
for e in fp['floor_types']['A']['structural_elements']:
    if e['type']=='column':
        n=nodes[e['nodes'][0]]
        x,y=p(n['x'],n['y'])
        orange=n['id'] in outrigger_ids
        d.rectangle((x-6,y-6,x+6,y+6),fill='#e7a449' if orange else '#566c88',outline='#654520' if orange else '#566c88',width=2)
text(276,165,'220 ft 11 in square floor plate',23,True)
text(121,994,'3 outer bays x 32.111 ft | 28.25 ft c/c central bay | 3 outer bays x 32.111 ft',19)
text(75,1033,'Central bay is 25.25 ft clear between 36 in column faces. No columns between the outrigger pair.',18)
text(905,192,'Coupled analysis model',28,True)
for i,(label,value) in enumerate([
    ('Columns','28 total; 8 outrigger columns'),
    ('Coarse floor grid','320 cells / 360 nodes per floor'),
    ('Tower floor mesh','12,800 membrane elements'),
    ('Requested / actual max','20 ft / 16.806 ft'),
    ('Root / chord elevations','325 ft and 350 ft'),
    ('Steel Fy','50 ksi'),
    ('Chords / diagonals','36 in / 18 in solid squares'),
    ('X/Y roof displacement','2.49183 in at 1,000 kip probe'),
    ('First global period','7.27783 s'),
    ('Local/global cut check','240 force comparisons passed'),
]):
    y=252+i*58
    text(905,y,label,19,True)
    text(905,y+24,value,20)
text(905,865,'Coarse mesh only.',23,True)
text(905,901,'Refinement was stopped by the user.',19)
text(905,944,'Member sizes remain placeholders;',19)
text(905,972,'no strength or buckling approval.',19)
text(38,1090,'Blue grid: actual analysis cells | Orange lines: truss planes in plan | Orange squares: retained outrigger columns',18)
target=ROOT/'tower_500ft_option_a_mesh_preview.png'
im.save(target)
print(target.name)
