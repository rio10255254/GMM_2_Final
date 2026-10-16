"""Add evidence pointers without changing existing measurement/model decisions."""
import copy
import hashlib
import json
import re
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];PROJECT=ROOT.parents[1]
DOC=ROOT/'reports/R152_THESIS_VISUAL_EVIDENCE_20261003'
info=json.loads((DOC/'DATA_AND_SELECTION.json').read_text(encoding='utf-8'))
receipt=json.loads((OUT/'package_receipt.json').read_text(encoding='utf-8'))
assert receipt['status']=='passed' and receipt['all_archive_member_checksums_match']
policy=PROJECT/'ESTIMATOR_POLICY.json';before=policy.read_bytes();data=json.loads(before.decode('utf-8-sig'))
baseline=copy.deepcopy(data['formal_baseline']);alternates=copy.deepcopy(data['approved_alternates'])
relative='Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_THESIS_VISUAL_EVIDENCE_20261003/'
data['artifact_index']['R152_thesis_visual_evidence_20261003']={
    'date':'2026-10-03','status':'complete','role':'thesis actual-image and response figures',
    'canonical_report':relative+'FIGURE_NOTES.md','combined_figures_pdf':relative+'THESIS_VISUAL_FIGURES.pdf',
    'archive':'Deliverables/R152_THESIS_VISUAL_EVIDENCE_20261003.zip',
    'archive_sha256':receipt['archive_sha256'],'PSF_count':25,'PSF_matrix_shape':[101,101],
    'PSF_bank_sha256':info['PSF_bank_sha256'],'source_MAT_sha256':info['source_MAT_sha256'],
    'native_image_frame':info['image_frame']['run']+'/1.bmp','native_R152_checkpoint_sha256':info['checkpoint_sha256'],
    'image_display_range':[0,1],'contours':{'scans':30,'fixed_frame_index':0,'main_object':5,
                                         'all9_supplement':True,'points_per_contour':64,'alignment':'translation only'},
    'section_placements':['6.1 Figure 6-3','after 6.2.3','6.2.4'],'PDF_rendered_pages_checked':5,
    'new_training':False,'image_postprocessing':False,
}
note='2026-10-03 R152 thesis actual visual evidence completed: exact 25 PSF matrices and calibration records, identical-coordinate RAW/native-MOSR real image and enlargement, and all 30 saved 64-point contours of fixed object 5 at the start position, with all-nine supplement. Common display scale; contour translation only. Five PDF pages rendered/reviewed; full source and ZIP contents verified. Visual evidence complements, rather than replaces, the complete 930-frame numerical validation.'
if note not in data['notes']:data['notes'].append(note)
assert data['formal_baseline']==baseline and data['approved_alternates']==alternates
assert policy.read_bytes()==before
policy.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
saved=json.loads(policy.read_text(encoding='utf-8'))
assert saved['formal_baseline']==baseline and saved['approved_alternates']==alternates
entry=saved['artifact_index']['R152_thesis_visual_evidence_20261003']
for field in ('canonical_report','combined_figures_pdf','archive'):assert (PROJECT/entry[field]).is_file()
for name in ('PROJECT_STATE.md','Experiments/INDEX.md','RECON_GALLERY.md'):
    content=(PROJECT/name).read_text(encoding='utf-8-sig');assert 'R152_THESIS_VISUAL_EVIDENCE_20261003' in content
gallery=(PROJECT/'RECON_GALLERY.md').read_text(encoding='utf-8-sig')
assert not re.search(r'<\s*(table|p|details|img|div|a)(\s|>)',gallery,re.I)
print('PASS: visual evidence registered, document/figure links valid, gallery remains plain Markdown')
