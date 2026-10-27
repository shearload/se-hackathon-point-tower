#!/usr/bin/env python3
"""Create one tower-summary JSON row from a PDF's selectable text and optional inputs."""
import argparse, json, re, sys, shutil, subprocess, tempfile
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
DEFAULT_TEMPLATE=ROOT/'sample_floor_plan_structure_template_blank_executable.json'
def num(s): return float(s.replace(',',''))
def labeled(patterns,text,cast=float):
    for p in patterns:
        m=re.search(p,text,re.I)
        if m:
            try: return cast(m.group(1).replace(',',''))
            except ValueError: pass
    return None
def ocr_pdf(pdf, dpi=300, language='eng'):
    """OCR scanned pages through local Poppler + Tesseract executables."""
    renderer = shutil.which('pdftoppm')
    if not renderer:
        # Poppler bundled with the Codex Python runtime, if available.
        candidates = [Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe']
        renderer = next((str(p) for p in candidates if p.is_file()), None)
    tesseract = shutil.which('tesseract')
    if not tesseract:
        candidates = [Path(r'C:/Program Files/Tesseract-OCR/tesseract.exe'), Path(r'C:/Program Files (x86)/Tesseract-OCR/tesseract.exe')]
        tesseract = next((str(p) for p in candidates if p.is_file()), None)
    if not renderer:
        return '', 'Poppler pdftoppm was not found; install Poppler or add pdftoppm to PATH.'
    if not tesseract:
        return '', 'Tesseract OCR was not found; install Tesseract OCR and add tesseract.exe to PATH.'
    chunks=[]
    with tempfile.TemporaryDirectory(prefix='floorplan_ocr_') as tmp:
        prefix=str(Path(tmp)/'page')
        render=subprocess.run([renderer,'-r',str(dpi),'-png',str(pdf),prefix],capture_output=True,text=True)
        if render.returncode:
            return '', 'PDF rasterization failed: '+(render.stderr.strip() or render.stdout.strip())
        images=sorted(Path(tmp).glob('page-*.png'))
        if not images:
            return '', 'PDF rasterization produced no page images.'
        for image in images:
            result=subprocess.run([tesseract,str(image),'stdout','-l',language,'--psm','11'],capture_output=True,text=True)
            if result.returncode:
                return '', 'Tesseract failed: '+(result.stderr.strip() or result.stdout.strip())
            chunks.append(result.stdout)
    return '\n'.join(chunks), None

def extract(pdf, use_ocr=True, dpi=300, language='eng'):
    reader=PdfReader(str(pdf)); pages=[]
    for page in reader.pages:
        try: pages.append(page.extract_text() or '')
        except Exception: pages.append('')
    text='\n'.join(pages)
    ocr_note=None
    # OCR only if the PDF has no usable selectable text.
    if use_ocr and len(re.sub(r'\s','',text)) < 30:
        ocr_text,ocr_note=ocr_pdf(pdf,dpi,language)
        if ocr_text.strip(): text=ocr_text
    row={'Name':pdf.stem,'Height (ft)':None,'City':None,'Program':None,'Base Footprint Dimensions (ft)':None,'Floors':None,'GFA (ft²)':None}
    row['Height (ft)']=labeled([r'(?:overall\s+)?height\s*(?:\(ft\))?\s*[:=]\s*([\d,]+(?:\.\d+)?)\s*(?:ft|feet)'],text)
    row['Floors']=labeled([r'(?:number of )?floors?\s*[:=]\s*(\d+)',r'(\d+)\s*(?:floors?|storeys|stories)\b'],text,int)
    row['GFA (ft²)']=labeled([r'(?:gross floor area|GFA)\s*(?:\(ft(?:\^?2|²)?\))?\s*[:=]\s*([\d,]+(?:\.\d+)?)'],text)
    for key,label in [('City','city'),('Program','program')]:
        m=re.search(r'\b'+label+r'\s*[:=]\s*([^\r\n,;]+)',text,re.I)
        if m: row[key]=m.group(1).strip()
    # Convert dimensions only when the unit is explicit in extracted PDF text.
    m=re.search(r'([\d,]+(?:\.\d+)?)\s*(mm|millimeters?|m|meters?|ft|feet)\s*[x×]\s*([\d,]+(?:\.\d+)?)\s*(mm|millimeters?|m|meters?|ft|feet)',text,re.I)
    if m:
        a,u1,b,u2=float(m.group(1).replace(',','')),m.group(2).lower(),float(m.group(3).replace(',','')),m.group(4).lower()
        if u1==u2:
            if u1.startswith('mm'): a,b=a/304.8,b/304.8
            elif u1=='m' or u1.startswith('meter'): a,b=a*3.280839895,b*3.280839895
            row['Base Footprint Dimensions (ft)']=f'{a:.2f} ft x {b:.2f} ft'
    return row,text,len(reader.pages),ocr_note
def main():
    p=argparse.ArgumentParser(description='Generate tower-summary JSON from a floor-plan PDF.')
    p.add_argument('pdf'); p.add_argument('--template',default=str(DEFAULT_TEMPLATE)); p.add_argument('--out')
    p.add_argument('--name'); p.add_argument('--height-ft',type=float); p.add_argument('--city'); p.add_argument('--program'); p.add_argument('--floors',type=int); p.add_argument('--gfa-sqft',type=float)
    p.add_argument('--footprint-ft',nargs=2,type=float,metavar=('WIDTH','LENGTH')); p.add_argument('--footprint-mm',nargs=2,type=float,metavar=('WIDTH','LENGTH')); p.add_argument('--no-prompt',action='store_true')
    p.add_argument('--no-ocr',action='store_true',help='Skip local Tesseract OCR'); p.add_argument('--ocr-dpi',type=int,default=300); p.add_argument('--ocr-language',default='eng')
    a=p.parse_args()
    try:
        pdf=Path(a.pdf); pdf=pdf if pdf.is_absolute() else ROOT/pdf; pdf=pdf.resolve()
        template=Path(a.template); template=template if template.is_absolute() else ROOT/template; template=template.resolve()
        out=Path(a.out) if a.out else ROOT/(pdf.stem+'_generated.json'); out=out if out.is_absolute() else ROOT/out; out=out.resolve()
        for path in (pdf,template,out): path.relative_to(ROOT)
        if not pdf.is_file(): raise ValueError(f'PDF not found: {pdf}')
        data,text,pages,ocr_note=extract(pdf,not a.no_ocr,a.ocr_dpi,a.ocr_language)
        overrides={'Name':a.name,'Height (ft)':a.height_ft,'City':a.city,'Program':a.program,'Floors':a.floors,'GFA (ft²)':a.gfa_sqft}
        for k,v in overrides.items():
            if v is not None: data[k]=v
        if a.footprint_ft: data['Base Footprint Dimensions (ft)']=f'{a.footprint_ft[0]:g} ft x {a.footprint_ft[1]:g} ft'
        if a.footprint_mm: data['Base Footprint Dimensions (ft)']=f'{a.footprint_mm[0]/304.8:.2f} ft x {a.footprint_mm[1]/304.8:.2f} ft'
        schema=json.loads(template.read_text(encoding='utf-8')); cols=schema.get('columns')
        if not isinstance(cols,list) or not all(isinstance(k,str) for k in cols): raise ValueError("Template must contain a string array named 'columns'.")
        row={k:data.get(k) for k in cols}
        if not a.no_prompt and sys.stdin.isatty():
            print(f'PDF pages: {pages}; selectable text characters: {len(text)}')
            if not text.strip(): print('No text was extracted. '+(ocr_note or 'Enter known values or press Enter to leave a field null.'))
            prompts=[('Height (ft)','Height (ft)'),('City','City'),('Program','Program'),('Base Footprint Dimensions (ft)','Footprint (ft), e.g. 106.63 ft x 157.48 ft'),('Floors','Floors'),('GFA (ft²)','GFA (ft²)')]
            for key,label in prompts:
                if key not in row or row[key] is not None: continue
                value=input(label+': ').strip()
                if value:
                    if key in ('Height (ft)','GFA (ft²)'): row[key]=num(value)
                    elif key=='Floors': row[key]=int(value)
                    else: row[key]=value
        out.write_text(json.dumps({'columns':cols,'rows':[row]},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Generated:',out); print('PDF pages:',pages,'| extracted text characters:',len(text))
        missing=[k for k,v in row.items() if v is None]
        if missing: print('Unfilled fields:',', '.join(missing),file=sys.stderr)
        if ocr_note and not text.strip(): print('OCR unavailable:',ocr_note,file=sys.stderr)
        if text.strip() and len(re.sub(r'\s','',text))>0: (out.parent/(out.stem+'_ocr.txt')).write_text(text,encoding='utf-8')
        return 0
    except Exception as e: print('Error:',e,file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
