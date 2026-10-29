from pathlib import Path
import json,hashlib,re,shutil
from PIL import Image
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]
R=Path(str(PROJECT_ROOT));P=R/'Experiments/R129_OpticalPriorHybrid/analysis/thesis_ready_20260920'
r=R/'Deliverables/Thesis_Handoffs/R129_Thesis_Rewrite_Ready_20260920'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(rel,o):(r/rel).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
cp=json.loads((r/'07_Checks/source_copies.json').read_text(encoding='utf-8'))
for x in cp:x['destination']=x['destination'].replace('\\','/')
derived_names={f'05_Paper_Figures/{x}.png' for x in ['F05_selected_nine','F07_contours_start','F08_contours_end']}
derived=[]
for x in cp:
 if x['destination'] in derived_names:
  derived.append(dict(original_copy=x,derived_output_sha256=sha(r/x['destination']),reason='Curated paper figure regenerated from saved source image/coordinates; unmodified original is in 04_Results/R129_Handoff.',generator='07_Checks/finish_materials.py'))
cp=[x for x in cp if x['destination'] not in derived_names]
for name in ['finish_materials.py','seal_materials.py']:
 src=P/name;dest='07_Checks/'+name;shutil.copy2(src,r/dest)
 cp.append(dict(source=str(src),destination=dest,sha256=sha(src)))
cp=list({x['destination']:x for x in cp}.values())
for x in cp:
 assert sha(Path(x['source']))==x['sha256'],x['source']
 assert sha(r/x['destination'])==x['sha256'],x['destination']
save('07_Checks/source_copies.json',cp);save('07_Checks/derived_figure_provenance.json',derived)
save('07_Checks/visual_review.json',dict(all_ten_figure_groups_reviewed=True,new_or_redrawn_this_turn=['F01','F02','F03','F04','F05','F07','F08'],unaltered_curated_source_figures_reviewed_in_current_conversation=['F06','F09','F10'],layout_fix='Separated legend from contour titles; original coordinates and source files preserved.',word_rendering='Unchanged source Word only; no rewritten DOCX delivered.'))
links=[]
for p in [r/'START_HERE.md',*list((r/'00_Plan').glob('*.md'))]:
 for x in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
  if x.startswith('http'):continue
  q=(p.parent/x).resolve();assert q.exists(),(p,x);links.append(str(q))
for p in (r/'05_Paper_Figures').glob('*.png'):
 with Image.open(p) as im:im.verify()
fg=pd.read_csv(r/'00_Plan/figure_caption_register.csv');assert len(fg)==10 and all((r/'05_Paper_Figures'/x).exists() for x in fg.file)
sections=pd.read_csv(r/'00_Plan/section_action_map.csv');assert len(sections)==131
for n in ['5.4.7','6.2.6']:assert sections[sections.text.str.startswith(n)].action.str.contains('刪除').all()
full=r/'04_Results/R129_Handoff'
for x in json.loads((full/'MANIFEST.json').read_text(encoding='utf-8')):assert sha(full/x['path'])==x['sha256']
summary=dict(status='writing_materials_ready_not_thesis_rewritten',ten_figure_groups=10,six_paper_tables=6,all_131_headings_mapped=True,authored_local_links_checked=len(links),copied_source_files_rechecked=len(cp),unchanged_handoff_payloads_verified=284,original_word_unchanged=True,new_ablation_experiments=False,large_array_policy='768 original arrays hashed in place; all metadata and seven input examples packaged.',full_image_policy='930 source/reconstruction pairs located; inherited hashes retained, not all images rehashed.')
save('07_Checks/final_preparation_review.json',summary)
items=[dict(path=str(p.relative_to(r)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(r.rglob('*')) if p.is_file() and p!=r/'MANIFEST.json']
save('MANIFEST.json',items)
print(json.dumps(summary,ensure_ascii=False,indent=2));print('files',len(items),'MiB',round(sum(x['bytes'] for x in items)/1024**2,2))
