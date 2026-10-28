"""Verify the selected four-condition poster from centers through publication files."""
from pathlib import Path
from collections import defaultdict
from statistics import median, stdev, mean
import csv, hashlib, io, json, zipfile
from lxml import etree
import openpyxl, pymupdf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'poster_final'
PPTX=OUT/'IMPACT2026_MOSR_StepSD_v4.pptx'
PDF=PPTX.with_suffix('.pdf')
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
def load_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
seqs=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']
methods=['Raw','Wiener','R152']
public={'Raw':'Raw','Wiener':'Wiener','R152':'MOSR'}
src=ROOT/'results/localization_improvement'
pairs=load_csv(src/'improved_pairs.csv')
centers=load_csv(src/'improved_centers.csv')
summary=load_csv(src/'improved_summary.csv')
locked=load_csv(ROOT/'sources/original_locked_pairs.csv')
cfg=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8'))
ci=defaultdict(dict)
for r in centers:ci[(r['sequence'],r['method'],int(r['frame_index']))][r['pillar_id']]=float(r['lsc_center_x_px'])
values={m:[] for m in methods};max_pair_error=0
for seq in seqs:
    expected={(int(r['start_frame_index']),int(r['end_frame_index'])) for r in locked if r['sequence']==seq}
    assert len(expected)==30
    for m in methods:
        rows=[r for r in pairs if r['sequence']==seq and r['method']==m]
        assert len(rows)==30 and {(int(r['start']),int(r['end'])) for r in rows}==expected
        steps=[]
        for r in rows:
            a=ci[(seq,m,int(r['start']))];b=ci[(seq,m,int(r['end']))]
            assert len(a)==len(b)==9 and a.keys()==b.keys()
            step=abs(median([(b[p]-a[p])*cfg['sequences'][seq]['object_um_per_px']*1000 for p in a]))
            max_pair_error=max(max_pair_error,abs(step-float(r['step_nm'])))
            steps.append(float(r['step_nm']))
        sd=stdev(steps)
        saved=float(next(r for r in summary if r['scope']==seq and r['method']==m)['step_sd_nm'])
        assert abs(sd-saved)<1e-9
        values[m].append(sd)
assert max_pair_error<1e-7
means={m:mean(v) for m,v in values.items()}
gains=[100*(r-s)/r for r,s in zip(values['Raw'],values['R152'])]
gain=100*(means['Raw']-means['R152'])/means['Raw']
assert all(s<min(r,w) for s,r,w in zip(values['R152'],values['Raw'],values['Wiener']))
with zipfile.ZipFile(PPTX) as z:
    p=etree.fromstring(z.read('ppt/presentation.xml'));size=p.find('p:sldSz',NS)
    assert (size.get('cx'),size.get('cy'))==('32400000','43200000')
    slide=etree.fromstring(z.read('ppt/slides/slide1.xml'))
    texts=slide.xpath('//a:t/text()',namespaces=NS);visible='\n'.join(texts)
    for forbidden in ['R152','60.8%','30 scans','30 repeats','52.6%','TW001','Xxxxx']:
        assert forbidden not in visible
    assert '19.5%' in visible and '9.8–24.1%' in visible and 'MOSR' in visible
    tables=slide.findall('.//a:tbl',NS);assert len(tables)==2
    rows=[[ ''.join(c.xpath('.//a:t/text()',namespaces=NS)) for c in row.findall('a:tc',NS)] for row in tables[1].findall('a:tr',NS)]
    for i in range(4):
        assert rows[i+1][1:]==[f'{values[m][i]:.2f}' for m in methods]+[f'{gains[i]:.1f}']
    assert rows[-1][1:]==[f'{means[m]:.2f}' for m in methods]+[f'{gain:.1f}']
    for tbl in tables:
        for pr in tbl.findall('.//a:tcPr',NS):
            assert pr.find('a:lnL/a:noFill',NS) is not None
            assert pr.find('a:lnR/a:noFill',NS) is not None
    charts=[n for n in z.namelist() if '/charts/' in n and n.endswith('.xml') and '/_rels/' not in n]
    assert len(charts)==1
    c=etree.fromstring(z.read(charts[0]));series=c.findall('.//c:barChart/c:ser',NS);assert len(series)==3
    for item,m in zip(series,methods):
        name=item.find('.//c:tx//c:v',NS).text
        assert name==public[m]
        nums=[float(v.text) for v in item.findall('.//c:val//c:pt/c:v',NS)]
        assert len(nums)==4 and max(abs(a-b) for a,b in zip(nums,values[m]))<5.1e-7
    books=[n for n in z.namelist() if n.endswith('.xlsx')];assert len(books)==1
    book=openpyxl.load_workbook(io.BytesIO(z.read(books[0])),data_only=True)
    assert book.active.max_row==5 and book.active.max_column==6
    for j,m in enumerate(methods):
        assert book.active.cell(1,2*j+2).value==public[m]
        assert all(abs(book.active.cell(i+2,2*j+2).value-values[m][i])<5.1e-7 for i in range(4))
    media=[z.read(n) for n in z.namelist() if '/media/' in n]
template=Path('C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026/4. Poster_Sample_2026 (2).pptx')
with zipfile.ZipFile(template) as z:assert z.read('ppt/media/image2.jpeg') in media
doc=pymupdf.open(PDF);assert len(doc)==1
page=doc[0];cm=[page.rect.width/72*2.54,page.rect.height/72*2.54]
assert abs(cm[0]-90)<.01 and abs(cm[1]-120)<.01
pdftext=page.get_text()
for required in ['19.5%','9.8','24.1%','MOSR','30','720','8.84','7.11','TABLE I.','TABLE II.','Fig. 1.','Fig. 2.']:
    assert required in pdftext,required
assert 'R152' not in pdftext and '60.8%' not in pdftext
blocks=page.get_text('blocks')
displacement=next(b for b in blocks if b[4].startswith('Displacement.'))
tablecaption=next(b for b in blocks if b[4].startswith('TABLE I.'))
assert tablecaption[1]-displacement[3]>20
fit=json.loads((ROOT/'poster_build/native_text_fit_v4.json').read_text(encoding='utf-8-sig'))
assert not any(r['overflow'] for r in fit)
validation=json.loads((ROOT/'poster_build/mosr_step_sd_validation_v4.json').read_text(encoding='utf-8'))
assert validation['presentationLayout']['warning_count']==0
assert validation['nativeChartValidation']['passed']
page.get_pixmap(matrix=pymupdf.Matrix(.65,.65)).save(ROOT/'poster_build/mosr_step_sd_pdf_review.png')
result={'passed':True,'scope':'four original conditions, 30 locked single steps each','repeat_scan_dataset_used':False,
        'statistic':'sample SD (denominator 29) per condition, arithmetic mean of four SDs',
        'max_center_to_step_replay_error_nm':max_pair_error,'sd_nm':{public[m]:v for m,v in values.items()},
        'means_nm':{public[m]:v for m,v in means.items()},'reductions_pct':gains,'mean_sd_reduction_pct':gain,
        'size_cm':cm,'native_chart_count':1,'editable_table_count':2,'embedded_workbook_count':1,
        'template_logo_unchanged':True,'native_powerpoint_opened':True,'native_text_overflow_count':0,
        'paper_code':None,'pptx_sha256':sha(PPTX),'pdf_sha256':sha(PDF),
        'source_hashes':{p.name:sha(p) for p in [src/'improved_pairs.csv',src/'improved_centers.csv',src/'improved_summary.csv',ROOT/'sources/original_locked_pairs.csv']}}
(ROOT/'poster_build/mosr_step_sd_final_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
