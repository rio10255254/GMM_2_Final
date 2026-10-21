from pathlib import Path
import argparse,cv2,numpy as np,torch
from model import Model
from utils import ROOT,load,sha,save,now,setup,model_config
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();setup(1482101);done=load(ROOT/'runs/formal_8192/training_complete.json');rec=done['checkpoint'];assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False);cfg=model_config();m=Model(cfg,ROOT).cuda().eval();m.load_state_dict(cp['model']);raw=cv2.imread(a.input,cv2.IMREAD_UNCHANGED);scale=255 if raw.dtype==np.uint8 else 65535;x=torch.from_numpy(raw.astype(np.float32)[None,None]/scale).cuda()
 with torch.inference_mode():y=m.forward_tiled(x).cpu().numpy()[0,0]
 with open(a.output,'xb') as h:np.savez_compressed(h,output=y)
 save(Path(a.output).with_suffix('.json'),dict(model=cfg['model_name'],checkpoint_sha256=rec['sha256'],native_output=True,postprocessing=False,output_sha256=sha(a.output),completed_utc=now()))
if __name__=='__main__':main()
