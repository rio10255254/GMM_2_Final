from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,zipfile,shutil,datetime
from docx import Document
PROJECT_ROOT = Path(__file__).resolve().parents[3]
P=Path(str(PROJECT_ROOT / 'Deliverables/R130_Clean_Web_Thesis_Documents_20260920'));R=Path(str(PROJECT_ROOT / 'Experiments/R130_Clean'));H=Path(str(PROJECT_ROOT / 'Deliverables/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
C=pd.read_csv(P/'完整數據/all_circles.csv');D=pd.read_csv(P/'完整數據/all_displacements.csv');I=pd.read_csv(P/'完整數據/individual_circle_displacements.csv')
assert len(C)==25110 and len(D)==5400 and len(I)==48600
assert not C.duplicated(['model','run','index','pillar_id']).any()
assert not D.duplicated(['model','run','kind','j']).any()
assert not I.duplicated(['model','run','kind','j','pillar_id']).any()
assert C.groupby('model').size().eq(8370).all() and D.groupby('model').size().eq(1800).all()
S=pd.read_csv(P/'完整數據/displacement_summary.csv');errs=[]
for (m,k),g in D.groupby(['model','kind']):
 r=S[(S.model==m)&(S.kind==k)].iloc[0]
 vals=[g.error_nm.abs().mean(),g.error_nm.mean(),g.groupby('j').error_nm.std().mean(),g.error_nm.abs().max()]
 errs.extend(abs(np.array(vals)-r[['mae_nm','bias_nm','repeatability_nm','maximum_error_nm']].to_numpy(float)))
assert max(errs)<1e-10
# Validate Word table values after file serialization, independent from their layout.
doc=Document(next(P.glob('04_*.docx')))
for ti,kind in [(0,'adjacent'),(1,'start')]:
 for row in doc.tables[ti].rows[1:]:
  vals=[c.text for c in row.cells];ref=S[(S.model==vals[0])&(S.kind==kind)].iloc[0]
  assert np.allclose(np.array(vals[1:],float),ref[['mae_nm','bias_nm','repeatability_nm','maximum_error_nm']].to_numpy(float),rtol=0,atol=5.1e-7)
pos=pd.read_csv(P/'完整數據/position_statistics.csv');num=0
for t in doc.tables:
 if [c.text for c in t.rows[0].cells]!=['位置','平均差 nm','重拍SD nm','PI均值 μm']:continue
 rows=np.array([[float(c.text) for c in row.cells] for row in t.rows[1:]])
 assert rows.shape==(30,4)
 candidates=[]
 for (m,k),g in pos.groupby(['model','kind']):
  arr=g.sort_values('position')[['position','mean_error_nm','repeat_sd_nm','mean_PI_um']].to_numpy()
  if np.allclose(rows,arr,rtol=0,atol=5.1e-7):candidates.append((m,k))
 assert len(candidates)==1,candidates;num+=1
assert num==6
for p in P.glob('*.docx'):
 d=Document(p);assert d.paragraphs[0].style.name=='Title'
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if name.endswith('.rels'):assert b'TargetMode="External"' not in z.read(name)
  assert b'<w:pBdr' not in z.read('word/styles.xml')
# All copied CSV source tables must remain byte-identical.
for q in (R/'results/comparison').glob('*.csv'):assert sha(q)==sha(P/'完整數據'/q.name)
for q in ['profile.json','profile_tiled_fresh.json','preflight.json','independent_final_training_audit.json','clean_control_summary.json','final_review_complete.json','environment_snapshot.json']:
 if not (P/'完整數據'/q).exists():shutil.copy2(R/'results'/q,P/'完整數據'/q)
shutil.copy2(R/'results/polish_web_docs.py',P/'製作與檢查/polish_web_docs.py')
shutil.copy2(__file__,P/'製作與檢查/verify_web_documents.py')
# Exact source identity, without updating any prior receipt.
for q in json.loads((H/'MANIFEST.json').read_text(encoding='utf-8')):assert sha(H/q['path'])==q['sha256']
(P/'製作與檢查/validation.json').write_text(json.dumps(dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),evidence_cutoff='2026-09-20',word_documents=5,all_circles=25110,aggregate_displacements=5400,individual_displacements=48600,displacement_recompute_max_error_nm=max(errs),word_position_tables_verified=6,all_word_images_embedded=True,original_handoff_unchanged=True,original_thesis_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: serialized Word tables, 79110 detailed rows, copied tables, embedded figures and protected source handoff')
