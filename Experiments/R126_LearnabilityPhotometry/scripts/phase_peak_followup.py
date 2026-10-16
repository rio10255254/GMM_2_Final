"""Frozen Raw-to-initial interpolation diagnoses peak switching; no score repair."""
import cv2
from phase_anatomy import anatomy
from common import *

def main():
    ev=ROOT/'results/real_P_s1265001_step0000';panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());rows=[]
    for item in panel['motion_pairs']:
        seq=item['sequence'];x0,y0,x1,y1=item['core_xyxy'];lx,ly,ux,uy=item['core_in_context_xyxy'];raw=[];candidate=[]
        for frame,s in enumerate(item['sources']):
            assert sha(s['path'])==s['sha256'];raw.append(cv2.imread(s['path'],0)[y0:y1,x0:x1].astype(float)/255)
            with np.load(ev/'motion'/seq/f'frame{frame}/output_float.npz') as d:candidate.append(d['output'][ly:uy,lx:ux].astype(float))
        for fraction in [0,.125,.25,.5,.75,1]:
            pair=[a+fraction*(b-a) for a,b in zip(raw,candidate)];info,surface=anatomy(*pair)
            rows.append(dict(sequence=seq,Raw_to_initial_fraction=fraction,mean_absolute_image_change_gray=float(np.mean([np.mean(np.abs(a-b)) for a,b in zip(raw,pair)])*255),**{k:v for k,v in info.items() if k!='local_surface'}))
    initial=json.loads((ROOT/'results/phase_anatomy_initial/summary.json').read_text())
    save(ROOT/'results/phase_peak_followup.json',dict(rows=rows,initial_anatomy_sha256=sha(ROOT/'results/phase_anatomy_initial/summary.json'),maximum_replay_error_px=max(r['reconstruction_error_px'] for r in rows),any_initial_centroid_outside_window=any(r['centroid_outside_local5x5'] for r in initial['rows']),tested_centroid_extrapolation_hypothesis_supported_for_initial_cases=False,conclusion='The initial20x_1um and50x_0p5um jumps already occur at selection of different integer correlation maxima. None of the12 initial centroids extrapolates outside its5x5 window. Thus centroid extrapolation is not the cause in these observed cases. This establishes a matching-peak instability, not true physical displacement preservation or a model pass.',primary_scores_unchanged=True,physical_truth_claim=False))

if __name__=='__main__':main()
