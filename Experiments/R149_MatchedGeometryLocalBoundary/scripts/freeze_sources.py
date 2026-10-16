"""Freeze the exact R149 formal-training sources after matched preflight."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import save,sha,now
FILES=('model.py','dataset.py','losses.py','train.py','training_policy.py','infer.py','utils.py','verify_package.py','optical/fullres_psf.py','config/model.json','config/train.json','config/data.json','calibration/measured_psf_bank.npz','calibration/BANK_LOCK.json','data/manifest.json','data/DATA_LOCK.json','scripts/prepare_matched_data.py','scripts/preflight.py','scripts/launch_r149.py')
def main():
 path=ROOT/'config/SOURCE_LOCK.json'
 if path.exists():raise FileExistsError(path)
 save(path,dict(purpose='R149 matched-geometry local-boundary formal scratch8192',files={x:sha(ROOT/x) for x in FILES},created_utc=now()));print('SOURCE_LOCKED',len(FILES))
if __name__=='__main__':main()
