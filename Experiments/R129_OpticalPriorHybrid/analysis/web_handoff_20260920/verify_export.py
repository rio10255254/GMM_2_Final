"""Preserve unsupported ISO timestamp text on XLSX export, then check every cell."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET,shutil,math,sys
import openpyxl
from PIL import Image,ImageDraw,ImageFont
import pymupdf
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.stdout.reconfigure(encoding='utf-8')
R=Path(str(PROJECT_ROOT));W=R/'Experiments/R129_OpticalPriorHybrid/results/web_handoff_20260920';O=R/'Deliverables/R129_Web_Thesis_Documents_20260920'
inputs=json.loads((W/'workbook_inputs.json').read_text(encoding='utf-8'));f=O/'05_完整數據.xlsx'
backup=W/'artifact_tool_before_timestamp_preservation.xlsx'
if not backup.exists():shutil.copy2(f,backup)
ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
nsrel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def col(n):
 s=''
 while n:n,a=divmod(n-1,26);s=chr(65+a)+s
 return s
with zipfile.ZipFile(f) as z:
 wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
 targets={x.attrib['Id']:x.attrib['Target'] for x in rels};parts={x.attrib['name']:targets[x.attrib['{'+nsrel+'}id']] for x in wb.find('{'+ns+'}sheets')}
 modifications={};fixed=0
 for item in inputs:
  if 'recorded_at' not in item['columns']:continue
  part=parts[item['name']];part=part.lstrip('/') if part.startswith('/') else 'xl/'+part
  root=ET.fromstring(z.read(part));cells={x.attrib['r']:x for x in root.iter('{'+ns+'}c')};j=item['columns'].index('recorded_at')
  for i,row in enumerate(item['rows'],2):
   val=row[j]
   if val is None:continue
   c=cells[col(j+1)+str(i)];c.set('t','inlineStr')
   for child in list(c):c.remove(child)
   t=ET.SubElement(ET.SubElement(c,'{'+ns+'}is'),'{'+ns+'}t');t.text=val;fixed+=1
  modifications[part]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
 tmp=f.with_suffix('.text_preserved.xlsx')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as target:
  for info in z.infolist():target.writestr(info,modifications.get(info.filename,z.read(info.filename)))
tmp.replace(f)
book=openpyxl.load_workbook(f,read_only=True,data_only=True);cells=0;maxdelta=0
for item in inputs:
 rows=book[item['name']].iter_rows(values_only=True);assert list(next(rows))==item['columns'],item['name'];count=0
 for actual,expected in zip(rows,item['rows'],strict=True):
  count+=1
  for a,e in zip(actual,expected,strict=True):
   cells+=1
   if isinstance(e,(int,float)):
    assert isinstance(a,(int,float)),(item['name'],count,a,e)
    maxdelta=max(maxdelta,abs(a-e));assert math.isclose(a,e,rel_tol=2e-14,abs_tol=1e-10),(item['name'],count,a,e)
   else:assert a==e or (a is None and e==''),(item['name'],count,a,e)
 assert count==len(item['rows']);print('Verified',item['name'],count,flush=True)
checks=dict(sheets=len(inputs)+1,source_data_sheets=len(inputs),cells_compared=cells,maximum_numeric_difference=maxdelta,all_rows_and_headers_matched=True,iso_timestamps_preserved_as_literal_text=fixed,export_fix='Artifact tool coerced ISO strings to serial numbers even with text format/string formula; targeted OOXML inline-string restoration preserves source timezone and fractional seconds. No other cell changed.')
(W/'xlsx_cell_verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype(r'C:\Windows\Fonts\msjh.ttc',18)
files=sorted((W/'xlsx_previews').glob('*.png'))
for start in range(0,len(files),5):
 sel=files[start:start+5];imgs=[Image.open(x).convert('RGB') for x in sel];width=max(x.width for x in imgs);height=sum(x.height+30 for x in imgs)
 out=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(out);y=0
 for p,im in zip(sel,imgs):draw.text((4,y),p.stem,font=font,fill='black');out.paste(im,(0,y+30));y+=im.height+30
 out.save(W/f'xlsx_contact_{start//5+1}.png')
for folder in sorted(W.glob('release_render_*')):
 doc=pymupdf.open(next(folder.glob('*.pdf')));print(folder.name,len(doc),[(i+1,len(p.get_text())) for i,p in enumerate(doc) if len(p.get_text())<70])
print(json.dumps(checks,ensure_ascii=False,indent=2))
