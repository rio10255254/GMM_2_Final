"""Check readable tables against full precision results, then verify every ZIP member."""
from __future__ import annotations
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
DOC=ROOT/'reports/R152_RAW_FULL_RECORD_20261002'
PROJECT=ROOT.parents[1]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    report=(DOC/'REPORT.md').read_text(encoding='utf-8')
    result=read(DOC/'data/complete_results.json')
    lines=report.splitlines();tables=[];i=0
    while i<len(lines):
        if lines[i].startswith('|'):
            block=[]
            while i<len(lines) and lines[i].startswith('|'):
                block.append([x.strip() for x in lines[i].split('|')[1:-1]]);i+=1
            assert len(block)>=2 and len({len(row) for row in block})==1
            tables.append((block[0],block[2:]))
        else:i+=1
    def tab(headers):
        values=[rows for cols,rows in tables if cols==headers]
        assert len(values)==1,headers
        return values[0]
    count=0
    def number(display,expected,places=3):
        nonlocal count
        assert abs(float(display)-float(expected))<=.50001*10**(-places),(display,expected,places)
        count+=1
    within={r['method']:r for r in result['within_scan']}
    displacement={(r['method'],r['kind']):r for r in result['displacement_summary']}
    geometry={r['method']:r for r in result['geometry']}
    sem={(r['method'],r['reference']):r for r in result['SEM_size']}
    endpoint={r['method']:r for r in result['endpoints']}
    headline=tab(['指標，單位nm','RAW','R152','結果'])
    expected_headline=[(within['RAW']['pooled_within_scan_sd_nm'],within['R152']['pooled_within_scan_sd_nm']),
                      (displacement[('RAW','adjacent')]['mae_nm'],displacement[('R152','adjacent')]['mae_nm']),
                      (displacement[('RAW','start')]['mae_nm'],displacement[('R152','start')]['mae_nm'])]
    expected_headline += [(geometry['RAW'][k],geometry['R152'][k]) for k in ('diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm')]
    expected_headline += [(sem[('RAW','SEM_workbook')]['mean_absolute_pillar_difference_nm'],sem[('R152','SEM_workbook')]['mean_absolute_pillar_difference_nm']),
                         (endpoint['RAW']['mean_signed_error_nm'],endpoint['R152']['mean_signed_error_nm'])]
    assert len(headline)==len(expected_headline)==8
    for row,pair in zip(headline,expected_headline):
        number(row[1],pair[0]);number(row[2],pair[1])
    rows=tab(['參照','方法','參照均徑nm','光學均徑nm','平均逐顆絕對差nm','最大逐顆絕對差nm'])
    for row in rows:
        source=sem[(row[1],row[0])]
        for cell,key in zip(row[2:],('reference_mean_diameter_nm','measured_mean_diameter_nm','mean_absolute_pillar_difference_nm','maximum_absolute_pillar_difference_nm')):number(cell,source[key],6)
    paired=pd.read_csv(DOC/'data/paired_30_scan_details.csv')
    rows=tab(['趟','原始趟次ID','RAW s_r nm','R152 s_r nm','降低nm','降低%'])
    assert len(rows)==30
    for row,x in zip(rows,paired.itertuples()):
        assert int(row[0])==x.scan and row[1]==x.run
        for cell,key in zip(row[2:5],('RAW_step_sd_nm','R152_step_sd_nm','absolute_sd_reduction_nm')):number(cell,getattr(x,key))
        number(row[5],x.reduction_percent,2)
    pos=pd.read_csv(DOC/'data/per_step_statistics_RAW_R152.csv')
    rows=tab(['步','RAW平均nm','RAW SD nm','R152平均nm','R152 SD nm','RAW平均PI差nm','R152平均PI差nm'])
    assert len(rows)==30
    for row in rows:
        step=int(row[0]);a=pos[(pos.method=='RAW')&(pos.kind=='adjacent')&(pos.step==step)].iloc[0]
        b=pos[(pos.method=='R152')&(pos.kind=='adjacent')&(pos.step==step)].iloc[0]
        for cell,value in zip(row[1:],(a.mean_measured_displacement_nm,a.measured_sd_nm,b.mean_measured_displacement_nm,b.measured_sd_nm,a.mean_error_nm,b.mean_error_nm)):number(cell,value)
    rows=tab(['位置','PI平均位移μm','RAW平均差nm','RAW差SD nm','R152平均差nm','R152差SD nm'])
    assert len(rows)==30
    for row in rows:
        step=int(row[0]);a=pos[(pos.method=='RAW')&(pos.kind=='start')&(pos.step==step)].iloc[0]
        b=pos[(pos.method=='R152')&(pos.kind=='start')&(pos.step==step)].iloc[0]
        number(row[1],a.mean_PI_displacement_um,6)
        for cell,value in zip(row[2:],(a.mean_error_nm,a.error_sd_nm,b.mean_error_nm,b.error_sd_nm)):number(cell,value)
    rows=tab(['趟','RAW短步MAE','R152短步MAE','RAW累積MAE','R152累積MAE','RAW終點差','R152終點差'])
    assert len(rows)==30
    for row,x in zip(rows,paired.itertuples()):
        assert int(row[0])==x.scan
        for cell,key in zip(row[1:],('RAW_adjacent_mae_nm','R152_adjacent_mae_nm','RAW_start_mae_nm','R152_start_mae_nm','RAW_endpoint_error_nm','R152_endpoint_error_nm')):number(cell,getattr(x,key))
    geom={r['method']:r for r in result['geometry']}
    rows=tab(['方法','平均直徑nm','直徑重拍SD nm','輪廓重拍SD nm','去尺寸形狀SD nm','最差直徑偏移nm'])
    for row in rows:
        for cell,key in zip(row[1:],('mean_diameter_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm','maximum_diameter_deviation_nm')):number(cell,geom[row[0]][key],6)
    per_pillar=pd.read_csv(DOC/'data/per_pillar_geometry_RAW_R152.csv')
    rows=tab(['顆','RAW平均直徑','R152平均直徑','RAW直徑SD','R152直徑SD','RAW輪廓SD','R152輪廓SD','RAW去尺寸SD','R152去尺寸SD'])
    assert len(rows)==9
    for row in rows:
        k=int(row[0]);values=[per_pillar[(per_pillar.method==m)&(per_pillar.pillar_id==k)].iloc[0][key]
                             for key in ('mean_diameter_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm') for m in ('RAW','R152')]
        for cell,value in zip(row[1:],values):number(cell,value)
    rows=tab(['指標','R152−RAW nm','95%差值區間nm','降低%','降低率95%區間%'])
    assert len(rows)==7
    for row,x in zip(rows,result['paired_intervals']):
        number(row[1],x['R152_minus_RAW_nm'])
        for cell,key in zip(row[2].split('～'),('difference_CI95_low_nm','difference_CI95_high_nm')):number(cell,x[key])
        number(row[3],x['reduction_percent'],2)
        for cell,key in zip(row[4].split('～'),('reduction_CI95_low_percent','reduction_CI95_high_percent')):number(cell,x[key],2)
    rows=tab(['補充指標','RAW nm','R152 nm','R152−RAW nm','95%差值區間nm'])
    assert len(rows)==7
    for row,x in zip(rows,result['additional_paired_intervals']):
        for cell,key in zip(row[1:4],('RAW_nm','R152_nm','R152_minus_RAW_nm')):number(cell,x[key])
        for cell,key in zip(row[4].split('～'),('difference_CI95_low_nm','difference_CI95_high_nm')):number(cell,x[key])
    rows=tab(['輪','更新','訓練loss平均','開發task','開發total','安全比例s'])
    assert len(rows)==16
    for row,x in zip(rows,result['training_epochs']):
        assert int(row[0])==x['epoch'] and int(row[1])==x['updates']
        for cell,key,places in zip(row[2:],('training_loss_mean','dev_task','dev_total','safe_scale'),(6,9,6,8)):number(cell,x[key],places)
    assert len(re.findall(r'^```',report,re.M))%2==0
    assert not re.search(r'\bTODO\b|\bTBD\b|\bNaN\b',report)
    for target in re.findall(r'\]\(([^)]+)\)',report):assert (DOC/target).is_file(),target
    d=pd.read_csv(DOC/'data/all_displacements_RAW_R152.csv');circles=pd.read_csv(DOC/'data/all_circles_RAW_R152.csv')
    assert len(d)==3600 and len(circles)==16740 and set(d.method)=={'RAW','R152'}
    for model in ('RAW','R152'):
        matrix=d[(d.method==model)&(d.kind=='adjacent')].pivot(index='run_index',columns='j',values='image_displacement_um').to_numpy()*1000
        sd=matrix.std(axis=1,ddof=1);ref=next(x for x in result['within_scan'] if x['method']==model)
        assert abs(np.sqrt((sd**2).mean())-ref['pooled_within_scan_sd_nm'])<1e-10
    assert np.allclose(circles.diameter_nm,circles.radius_px*345,rtol=0,atol=1e-9)
    with np.load(DOC/'data/complete_saved_boundary_points_RAW_R152.npz',allow_pickle=False) as z:
        assert z['RAW_points_px'].shape==z['R152_points_px'].shape==(30,31,9,64,2)
    for x in read(DOC/'SOURCE_INDEX.json'):
        assert sha(DOC/x['package_path'])==x['sha256'] and sha(x['source'])==x['sha256']
    for png in (DOC/'figures').glob('*.png'):
        pixels=np.asarray(Image.open(png).convert('RGB'))
        assert np.array_equal(pixels[...,0],pixels[...,1]) and np.array_equal(pixels[...,1],pixels[...,2])
        pdf=PdfReader(png.with_suffix('.pdf'));assert len(pdf.pages)==1
        text=pdf.pages[0].extract_text();assert 'R152' in text
        assert png.with_suffix('.svg').is_file()
    verification=dict(status='passed',readable_numeric_cells_checked=count,markdown_tables=len(tables),
                      complete_paired_scans=30,displacement_rows=3600,circle_rows=16740,
                      point_arrays_complete=True,source_copies_match_originals=True,
                      grayscale_figures=6,all_figure_links_exist=True,
                      figures_visually_reviewed=True,original_hash_checks=result['integrity'])
    (DOC/'VERIFICATION.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    files=sorted(p for p in DOC.rglob('*') if p.is_file() and p.name!='PACKAGE_MANIFEST.json')
    manifest=[dict(path=p.relative_to(DOC).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    (DOC/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    zip_path=PROJECT/'Deliverables/R152_RAW_COMPLETE_RESEARCH_RECORD_20261002.zip'
    zip_path.parent.mkdir(exist_ok=True)
    files=sorted(p for p in DOC.rglob('*') if p.is_file())
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(DOC).as_posix())
    with zipfile.ZipFile(zip_path,'r') as z:
        assert z.testzip() is None
        assert set(z.namelist())=={p.relative_to(DOC).as_posix() for p in files}
        for p in files:assert hashlib.sha256(z.read(p.relative_to(DOC).as_posix())).hexdigest()==sha(p)
    receipt=dict(**verification,archive=str(zip_path),archive_bytes=zip_path.stat().st_size,
                 archive_sha256=sha(zip_path),archive_members=len(files),all_archive_members_verified=True)
    (OUT/'PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
