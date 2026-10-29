"""Explain historical-pixel differences without changing the common comparison settings."""
from r135_common import *
import adapters,cv2
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    out=ROOT/'results/legacy_arithmetic';out.mkdir(exist_ok=False);plan=load(ROOT/'config/plan.json');original=adapters.module
    def isolated(name,path):
        m=original(name,path)
        if name=='legacy_native_inference':m.build_output_dir=lambda *a,**k:out/'native_loader'
        return m
    adapters.module=isolated;predict,details=adapters.build('V42_old');rows=[]
    for seq,spec in plan['configuration']['sequences'].items():
        f=next(f for f in plan['frames'] if f['sequence']==seq);raw=cv2.imread(str(PROJECT_ROOT / f['source']['path']),0);hist=cv2.imread(str(Path(PROJECT_ROOT / spec['v42_dir'])/Path(PROJECT_ROOT / f['source']['path']).name),0)
        for flag in [False,True]:
            torch.backends.cudnn.allow_tf32=flag;value=predict(raw);preview=np.rint(value*255).clip(0,255).astype(np.uint8);rows.append(dict(sequence=seq,cudnn_allow_tf32=flag,historical_equal=bool(np.array_equal(preview,hist)),different_pixels=int(np.count_nonzero(preview!=hist)),max_gray=float(abs(preview.astype(float)-hist.astype(float)).max())))
    torch.backends.cudnn.allow_tf32=False;verify();save(out/'complete.json',dict(rows=rows,comparison_remains_strict_FP32=True,no_existing_record_modified=True,source=record(__file__)));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
