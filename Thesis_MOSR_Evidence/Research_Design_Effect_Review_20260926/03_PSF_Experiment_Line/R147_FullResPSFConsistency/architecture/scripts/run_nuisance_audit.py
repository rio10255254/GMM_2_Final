from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
for model in ('r147','r146','r140'):
 if (ROOT/f'results/internal_audit/nuisance_{model}_complete.json').exists():continue
 subprocess.run([sys.executable,'-u','-B',str(ROOT/'scripts/audit_nuisance.py'),'--model',model],cwd=ROOT,check=True)
print('NUISANCE_ALL_COMPLETE',flush=True)
