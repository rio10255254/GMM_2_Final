"""Actual trained checkpoints, actual real input, whole vs tiled numerical parity."""
import cv2
from common import *
from inference.tiling import tiled_forward

def main():
    setup();panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());rows=[]
    for arm,seed,exposure in [('P',1265001,13),('Q',1265002,24)]:
        cp=ROOT/'runs'/f'photo_{arm}_s{seed}'/'step0128.pth';payload=torch.load(cp,map_location='cpu',weights_only=True)
        m=new_model(True,seed);learned={k:v for k,v in payload['model_state'].items() if not k.startswith('observation.')};loaded=m.load_state_dict(learned,strict=False)
        assert not loaded.unexpected_keys and all(k.startswith('observation.') for k in loaded.missing_keys);m.eval()
        item=next(x for x in panel['full_images'] if x['name']==f'sem_optical_exposure{exposure}');assert sha(item['source']['path'])==item['source']['sha256']
        a=cv2.imread(item['source']['path'],0)[128:640,128:640].astype(np.float32)/255
        source=torch.from_numpy(a)[None,None].cuda()
        with torch.inference_mode():
            full=m(source);tile=tiled_forward(m,source,core=256,halo=m.required_halo,origin=(31,17));error=float((full-tile).abs().max())
        rows.append(dict(arm=arm,seed=seed,checkpoint_sha256=sha(cp),source=item['source'],source_window=[128,640,128,640],tile_origin=[31,17],tile_core=256,halo=m.required_halo,maximum_absolute_difference=error,tolerance=3e-6,passed=error<=3e-6,real_model_usefulness_claimed=False))
        print(json.dumps(rows[-1]),flush=True)
    save(ROOT/'results/learned_tile_verification.json',dict(rows=rows,passed=all(x['passed'] for x in rows),fixed_model_source=sha(R125/'prototype/network.py')))
    if not all(x['passed'] for x in rows):raise ValueError('Actual learned tile parity failure')

if __name__=='__main__':main()
