"""Fixed sources and common protocol for the committee-requested comparison."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
MOSR_SOURCE=PROJECT/'Experiments/R152_R148v2_SafeAdaptivePSF'
PACK=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004'
RECORD=MOSR_SOURCE/'reports/R152_RAW_FULL_RECORD_20261002'
PUBLIC=ROOT/'reports'
METHODS=['RAW','Wiener','U-Net','EDSR-x1','RDN-x1','RCAN-x1','NAFNet','SwinIR','Restormer','MambaIRv2','USRNet-x1','MOSR']
SCALE_NM=172.5
BOOTSTRAP_SEED=20261002
BOOTSTRAP_DRAWS=20000
TRAIN_SEED=1482101
UPDATES=8192


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def training_config():
    if str(PACK) not in sys.path:sys.path.insert(0,str(PACK))
    from settings import TRAIN_CONFIG
    cfg=deepcopy(TRAIN_CONFIG)
    cfg.update(model_seed=TRAIN_SEED,updates=UPDATES,epochs=16,
               loss={'image':1.,'gradient':.2,'pair_output':.2,'boundary':.2,'observation':.01},
               original_data_epoch_cycle=16,checkpoint_selection='fixed_final_update',
               external_pretrained_weights=False)
    return cfg
