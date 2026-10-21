"""Frozen E42 path interventions for one existing SEM-linked exposure."""
from pathlib import Path
import sys
import json
import numpy as np
import cv2
import torch
OUT=Path(__file__).resolve().parent
W=OUT.parents[1]
sys.path.insert(0,str(W))
from inference.run import load,read,tiled
from model.ops import warp_local
from model.network import continuous_width


class PathView(torch.nn.Module):
    def __init__(self,model,variant):
        super().__init__(); self.model=model; self.variant=variant
        self.minimum_halo_px=model.minimum_halo_px
    def forward(self,x):
        d=self.model.forward_details(x)
        if self.variant=='base':return d.output
        if self.variant=='no_detail':return d.geometry_output.clamp(0,1)
        if self.variant=='no_width':return (warp_local(x,d.flow)+d.detail).clamp(0,1)
        if self.variant=='no_shift':
            return (continuous_width(x,d.width_gain,d.sdf,d.normals,self.model.config['local_range_window'])+d.detail).clamp(0,1)
        raise ValueError(self.variant)


def main():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    source=W.parent/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/13.bmp'
    raw=read(source);device='cuda' if torch.cuda.is_available() else 'cpu'
    model=load(W/'runs/formal_B_s1195001/weights/epoch_042.pth',device)
    target=OUT/'sem_paths';target.mkdir(exist_ok=False)
    cv2.imwrite(str(target/'Raw.png'),raw)
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(device)
    rows=[]
    for name in ['base','no_detail','no_width','no_shift']:
        with torch.inference_mode():output=tiled(PathView(model,name),x)[0,0].cpu().numpy()
        out=np.rint(output*255).clip(0,255).astype(np.uint8)
        cv2.imwrite(str(target/f'{name}.png'),out)
        info={'variant':name,'mean_change_gray':float(np.abs(out.astype(float)-raw).mean())}
        if name=='base':
            old=read(W/'results/formal_sem/reconstructions/13.bmp')
            info['old_base_max_gray_difference']=int(np.abs(out.astype(int)-old.astype(int)).max())
            info['old_base_different_pixels']=int((out!=old).sum())
        rows.append(info)
        print(info,flush=True)
    (target/'render_audit.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
