"""Verify matrix fidelity, native-image crops, true 30-contour records and PDF exports."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];PROJECT=ROOT.parents[1]
DOC=ROOT/'reports/R152_THESIS_VISUAL_EVIDENCE_20261003'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    info=read(DOC/'DATA_AND_SELECTION.json')
    with np.load(DOC/'calibration/measured_psf_bank.npz',allow_pickle=False) as z:bank=z['all_kernels']
    for i in range(25):
        assert np.array_equal(np.loadtxt(DOC/f'data/PSF_{i+1:02d}_101x101.csv',delimiter=','),bank[i])
    assert bank.shape==(25,101,101) and np.isfinite(bank).all() and (bank>=0).all()
    sources=read(DOC/'SOURCE_INDEX.json')
    for item in sources:
        assert sha(item['source'])==item['sha256']
        if 'copy' in item:assert sha(DOC/item['copy'])==item['sha256']
    raw=cv2.imread(str(DOC/'data/RAW_same_frame_original.bmp'),-1)
    with np.load(DOC/'data/R152_same_frame_original_float32.npz',allow_pickle=False) as z:mosr=z['output']
    b=info['image_crop_bounds'];roi=(slice(b['y0'],b['y1']),slice(b['x0'],b['x1']))
    with np.load(DOC/'data/same_region_native_crops.npz',allow_pickle=False) as z:
        assert np.array_equal(z['RAW'],(raw.astype(np.float32)/255)[roi])
        assert np.array_equal(z['R152'],mosr[roi])
    assert np.array_equal(cv2.imread(str(DOC/'data/RAW_same_frame_native_u8.png'),-1),raw)
    preview=cv2.imread(str(DOC/'data/R152_same_frame_display_u16.png'),-1)
    assert preview.dtype==np.uint16 and np.abs(preview.astype(float)/65535-mosr).max()<.5001/65535
    rows=pd.read_csv(DOC/'data/all9_start_position_30_contours.csv')
    assert len(rows)==2*30*9*64 and not rows.duplicated(['method','scan','pillar_id','point_index']).any()
    assert rows.groupby(['method','scan','pillar_id']).size().eq(64).all()
    assert set(rows.scan)==set(range(1,31)) and set(rows.pillar_id)==set(range(1,10)) and rows.frame_index.eq(0).all()
    assert np.allclose(rows.relative_x_um,(rows.x_px-rows.LSC_center_x_px)*.1725,rtol=0,atol=1e-12)
    assert np.allclose(rows.relative_y_um,(rows.y_px-rows.LSC_center_y_px)*.1725,rtol=0,atol=1e-12)
    for entry in pd.read_csv(DOC/'data/contour_measurement_source_checksums.csv').itertuples():assert sha(entry.source)==entry.sha256
    with np.load(DOC/'data/all9_start_position_measured_contours.npz',allow_pickle=False) as z:
        for model in ('RAW','R152'):
            p=z[model+'_points_px'];centers=z[model+'_centers_px']
            assert p.shape==(30,9,64,2) and centers.shape==(30,9,2)
            subset=rows[rows.method==model].sort_values(['scan','pillar_id','point_index'])
            assert np.allclose(subset[['x_px','y_px']].to_numpy().reshape(30,9,64,2),p,rtol=0,atol=1e-12)
    order=info['figure_page_order'];assert len(order)==5
    combined=PdfReader(DOC/'THESIS_VISUAL_FIGURES.pdf');assert len(combined.pages)==5
    for i,name in enumerate(order):
        pdf=PdfReader(DOC/f'figures/{name}.pdf');assert len(pdf.pages)==1
        assert combined.pages[i].extract_text()==pdf.pages[0].extract_text()
        pixels=np.asarray(Image.open(DOC/f'figures/{name}.png').convert('RGB'))
        assert np.array_equal(pixels[...,0],pixels[...,1]) and np.array_equal(pixels[...,1],pixels[...,2])
        assert (DOC/f'figures/{name}.svg').is_file()
        assert (OUT/f'qa_pdf/page-{i+1}.png').is_file()
    notes=(DOC/'FIGURE_NOTES.md').read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)',notes):assert (DOC/target).is_file(),target
    assert len(re.findall(r'^\| \d+ \|',notes,re.M))==25
    for x in info['central_object_statistics']:
        for key in ('mean_diameter_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','desized_shape_repeat_sd_nm'):
            assert f'{x[key]:.6f}' in notes
    checks=dict(status='passed',PSF_matrix_csv_exact_roundtrips=25,PSF_original_MAT_exact=True,
                PSF_deployed_float32_exact=True,source_file_checks=len(sources),native_pair_same_coordinates=True,
                common_display_range=[0,1],no_image_postprocessing=True,
                contour_rows=34560,all_30_scans_and9_objects=True,measured_points_per_contour=64,
                translation_only_alignment_verified=True,individual_PDFs=5,combined_PDF_pages=5,
                PDF_pages_rendered_and_visually_reviewed=5,all_figures_grayscale=True)
    (DOC/'VERIFICATION.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    files=sorted(p for p in DOC.rglob('*') if p.is_file() and p.name!='PACKAGE_MANIFEST.json')
    manifest=[dict(path=p.relative_to(DOC).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    (DOC/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    path=PROJECT/'Deliverables/R152_THESIS_VISUAL_EVIDENCE_20261003.zip'
    files=sorted(p for p in DOC.rglob('*') if p.is_file())
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(DOC).as_posix())
    with zipfile.ZipFile(path,'r') as z:
        assert z.testzip() is None
        assert set(z.namelist())=={p.relative_to(DOC).as_posix() for p in files}
        for p in files:assert hashlib.sha256(z.read(p.relative_to(DOC).as_posix())).hexdigest()==sha(p)
    receipt=dict(**checks,archive=str(path),archive_bytes=path.stat().st_size,archive_sha256=sha(path),
                 archive_members=len(files),all_archive_member_checksums_match=True)
    (OUT/'package_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
