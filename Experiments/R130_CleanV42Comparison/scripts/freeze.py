"""Freeze sources after actual preflight succeeds, before the one formal run."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    assert load(ROOT/'results/preflight/complete.json')['passed']
    files=[*ROOT.glob('model/*.py'),*ROOT.glob('training/*.py'),*ROOT.glob('scripts/*.py'),*ROOT.glob('validation/*.py'),*ROOT.glob('validation/*.m'),*ROOT.glob('validation/inputs/*.png'),ROOT/'validation/panel.json',ROOT/'validation/sem_reference.mat',ROOT/'calibration/shared_psf.mat',ROOT/'config/architecture.json',ROOT/'config/training.json',ROOT/'config/provenance.json']
    sources=[record(p) for p in files]+load(ROOT/'config/provenance.json')['protected']
    save(ROOT/'config/frozen.json',dict(created_utc=now(),sources=sources,preflight=record(ROOT/'results/preflight/complete.json'),same_clean_training_sources=True,one_fresh_V42_only=True,existing_R129_fixed=True))
    print('Frozen',len(sources),'source records')
if __name__=='__main__':main()
