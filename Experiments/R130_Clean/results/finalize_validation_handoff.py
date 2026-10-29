from pathlib import Path
import json,hashlib,zipfile,subprocess,tempfile,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[3]
P=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920'))
R=Path(str(PROJECT_ROOT / 'Experiments/R130_Clean'))
a=P/'01_Raw_R130_Comparison'
D=pd.read_csv(a/'all_circles.csv');runs=json.loads((P/'03_Sampling_and_SEM/capture_plan.json').read_text())['runs']
for j in [0,30]:
 fig,axes=plt.subplots(3,3,figsize=(11,11))
 for model,color in [('Raw','#777777'),('R130-Clean','#E47722')]:
  curves=[]
  for run in runs:
   name=run['run'];rows=D[(D.model==model)&(D.run==name)&(D['index']==j)].sort_values('pillar_id')
   with np.load(P/'05_Verification_and_Sources/measured_centers'/model/(name+'.npz')) as z:points=z['points'][j]
   curves.append((points-rows[['center_x_px','center_y_px']].to_numpy()[:,None,:])*172.5)
  curves=np.array(curves)
  for k,ax in enumerate(axes.flat):
   for r in curves:
    q=np.vstack([r[k],r[k,0]]);ax.plot(q[:,0],q[:,1],color=color,alpha=.18,lw=.65)
   ax.plot([],[],color=color,label=model)
   ax.set(title=f'Pillar {k+1}',xlim=(-1850,1850),ylim=(1850,-1850),aspect='equal',xlabel='Centered x (nm)',ylabel='Centered y (nm)');ax.grid(alpha=.15)
 axes[0,0].legend(fontsize=8)
 fig.suptitle(f'Position {j}: all 30 measured contours, each centered on its fitted circle\nOriginal 64 boundary points; centering removes translation only',fontsize=12)
 fig.tight_layout(rect=(0,0,1,.95));fig.savefig(a/f'figures/contours_position{j:02d}.png',dpi=160);fig.savefig(a/f'figures/contours_position{j:02d}.svg');plt.close(fig)
with (a/'README.md').open('a',encoding='utf-8') as q:q.write('\n## 30 趟實際輪廓疊圖\n每條線來自一次實際量測的 64 個邊界點；各自移至擬合圓心，只扣平移，不扣尺寸。\n\n![起點輪廓](figures/contours_position00.png)\n![終點輪廓](figures/contours_position30.png)\n')
shutil.copy2(__file__,P/'06_Script_Reference/finalize_validation_handoff.py')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
# Seal the final delivery after adding the requested contour visualizations.
items=[dict(path=p.relative_to(P).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
(P/'MANIFEST.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run(['python',str(P/'verify_package.py')],check=True)
# Test the read-only verifier's failure behavior using a disposable independent sample.
with tempfile.TemporaryDirectory(prefix='r130_verify_test_') as temp:
 t=Path(temp);shutil.copy2(P/'verify_package.py',t/'verify_package.py');(t/'sample.txt').write_text('original')
 m=[dict(path=n,sha256=sha(t/n)) for n in ['verify_package.py','sample.txt']];(t/'MANIFEST.json').write_text(json.dumps(m))
 for condition in ['unchanged','modified','missing']:
  if condition=='modified':(t/'sample.txt').write_text('changed')
  if condition=='missing':(t/'sample.txt').unlink()
  result=subprocess.run(['python',str(t/'verify_package.py')],capture_output=True,text=True)
  assert result.returncode==(0 if condition=='unchanged' else 1),(condition,result.stdout)
zip_path=P.with_suffix('.zip');assert not zip_path.exists()
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(P.rglob('*')):
  if p.is_file():z.write(p,P.name+'/'+p.relative_to(P).as_posix())
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read(P.name+'/MANIFEST.json'))
 assert len(z.namelist())==len(manifest)+1
 for item in manifest:assert hashlib.sha256(z.read(P.name+'/'+item['path'])).hexdigest()==item['sha256']
zip_path.with_suffix('.zip.sha256').write_text(sha(zip_path)+'  '+zip_path.name+'\n',encoding='ascii')
print(json.dumps(dict(files=len(items)+1,payload_files=len(items),zip_MB=zip_path.stat().st_size/1024**2,zip_all_entries_verified=True,modified_and_missing_file_detection_passed=True,zip=str(zip_path)),ensure_ascii=False))
