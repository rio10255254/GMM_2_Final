"""Resume fixed internal tests, without training or selecting a candidate."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import save,sha,now
def main():
 phases=[('r147','gradients')]+[(m,p) for m in ('r147','r146','r140') for p in ('crops','shifts')]
 for m,p in phases:
  marker=ROOT/'results/internal_audit'/('gradients_complete.json' if p=='gradients' else f'{p}_{m}_complete.json')
  if marker.exists():continue
  save(ROOT/'results/internal_audit/status.json',dict(state='running',model=m,phase=p,utc=now()))
  subprocess.run([sys.executable,'-u','-B',str(ROOT/'scripts/audit_internal.py'),'--model',m,'--phase',p],cwd=ROOT,check=True)
 save(ROOT/'results/internal_audit/status.json',dict(state='complete',completed_utc=now(),script_sha256=sha(ROOT/'scripts/audit_internal.py')))
if __name__=='__main__':main()
