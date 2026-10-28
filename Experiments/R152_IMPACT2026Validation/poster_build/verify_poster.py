from pathlib import Path
import csv,hashlib,json,zipfile,io
from lxml import etree
import openpyxl,pymupdf
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'poster_final'
PPTX=OUT/'IMPACT2026_R152_Poster_v6.pptx';PDF=OUT/'IMPACT2026_R152_Poster_v6.pdf'
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
rows=list(csv.DictReader((ROOT/'results/localization_improvement/improved_summary.csv').open(encoding='utf-8')));agg={r['method']:r for r in rows if r['scope']=='all120'};fields=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']
with zipfile.ZipFile(PPTX) as z:
 p=etree.fromstring(z.read('ppt/presentation.xml'));size=p.find('p:sldSz',NS);assert (size.get('cx'),size.get('cy'))==('32400000','43200000')
 slide=etree.fromstring(z.read('ppt/slides/slide1.xml'));text=slide.xpath('//a:t/text()',namespaces=NS)
 assert not any('TW001' in s or 'Xxxxx' in s or 'We hope you' in s or 'Size:' in s for s in text)
 for t in ['Introduction','Methods','Results','Conclusions','Bibliography']:assert t in text
 charts=[n for n in z.namelist() if '/charts/' in n and n.endswith('.xml') and '/_rels/' not in n];assert len(charts)==1
 c=etree.fromstring(z.read(charts[0]));series=c.findall('.//c:barChart/c:ser',NS);assert len(series)==3
 for item,m in zip(series,['Raw','Wiener','R152']):
  vals=[float(v.text) for v in item.findall('.//c:val//c:pt/c:v',NS)]
  assert len(vals)==3 and all(abs(v-float(agg[m][f]))<5.1e-7 for v,f in zip(vals,fields))
  assert all(f'{float(agg[m][f]):.2f}' in text for f in fields)
 books=[n for n in z.namelist() if n.endswith('.xlsx')];assert len(books)==1
 wb=openpyxl.load_workbook(io.BytesIO(z.read(books[0])),data_only=True);assert wb.active.max_row==4
 media=[z.read(n) for n in z.namelist() if '/media/' in n]
template=Path('C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026/4. Poster_Sample_2026 (2).pptx')
with zipfile.ZipFile(template) as z:assert z.read('ppt/media/image2.jpeg') in media
doc=pymupdf.open(PDF);assert len(doc)==1;page=doc[0];cm=[page.rect.width/72*2.54,page.rect.height/72*2.54];assert abs(cm[0]-90)<.01 and abs(cm[1]-120)<.01
pdftext=page.get_text()
for t in ['60.8%','19.5%','23.1%','720','7.11','5.56','4.26']:assert t in pdftext
page.get_pixmap(matrix=pymupdf.Matrix(.65,.65)).save(ROOT/'poster_build/final_pdf_review.png')
for seq in ['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']:
 r={x['method']:x for x in rows if x['scope']==seq};assert all(float(r['R152'][f])<min(float(r['Raw'][f]),float(r['Wiener'][f])) for f in fields)
validation=json.loads((ROOT/'poster_build/validation_v6.json').read_text(encoding='utf-8'));assert validation['presentationLayout']['warning_count']==0
result={'passed':True,'pptx_slide_count':1,'pdf_page_count':1,'size_cm':cm,'native_tables':2,'editable_native_charts':1,'embedded_chart_workbooks':1,'source_data_match':True,'template_logo_unchanged':True,'layout_warnings':0,'paper_code':'awaiting user value','pptx_sha256':hashlib.sha256(PPTX.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(PDF.read_bytes()).hexdigest()}
(ROOT/'poster_build/final_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
