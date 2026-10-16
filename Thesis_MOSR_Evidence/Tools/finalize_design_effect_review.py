from pathlib import Path
import csv,hashlib,json
ROOT=Path(r'D:\GMM_2_Final\Thesis_MOSR_Evidence\Research_Design_Effect_Review_20260926')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
m=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'));known={r['destination'] for r in m['records']}
for p in ROOT.rglob('*'):
 if not p.is_file() or p.name in ('MANIFEST.json','MANIFEST.csv','VERIFICATION_RESULT.json'):continue
 rel=str(p.relative_to(ROOT))
 if rel not in known:m['records'].append(dict(role='generated_cross_round_review',source='generated',destination=rel,bytes=p.stat().st_size,sha256=sha(p)));known.add(rel)
m['files']=len(m['records']);m['bytes']=sum(r['bytes'] for r in m['records']);(ROOT/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'MANIFEST.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=['role','source','destination','bytes','sha256']);w.writeheader();w.writerows(m['records'])
print(m['files'],m['bytes'])
