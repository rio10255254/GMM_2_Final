"""Run all generation while denying access to old experiments and bundled TIFFs."""
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True

PROJECT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PACK=PROJECT/'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004'


def normalized(path):
    return os.path.normcase(os.path.abspath(os.fsdecode(path)))


forbidden=[normalized(PROJECT/'Experiments'),normalized(PROJECT/'Thesis_MOSR_Evidence'),
           normalized(PROJECT/'Deliverables/Standalone_Models/R152_Standalone_20261004'),normalized(PACK/'data')]
allowed=normalized(OUT)


def beneath(path,root):
    return path==root or path.startswith(root+os.sep)


def audit(event,args):
    if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    path=normalized(args[0])
    if beneath(path,allowed):
        return
    if any(beneath(path,root) for root in forbidden):
        raise RuntimeError('Independent regeneration attempted an old-source access: '+path)


sys.addaudithook(audit)
sys.path.insert(0,str(PACK))
from generate_data import main


if __name__=='__main__':
    main(['--output-dir',str(OUT/'regenerated_bank'),'--workers','4'])
