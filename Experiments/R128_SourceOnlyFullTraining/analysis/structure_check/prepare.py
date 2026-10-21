"""Freeze source-selected structure features before reading new model outputs."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import *
import cv2,numpy as np

def main():
    out=ROOT/'results/structure_check';out.mkdir(parents=True,exist_ok=False)
    cp=ROOT/'runs/P_s1285002/checkpoints/step8192.pth'
    expected=load(ROOT/'results/final_review/comparison_verification.json')['checks']['checkpoint'];assert sha(cp)==expected['sha256']
    panel=load(R125/'results/real_panel_v2/frozen_panel.json')
    sources=[];features=[];pairs=[]
    for item in panel['motion_pairs']:
        seq=item['sequence'];files=sorted(Path(item['sources'][0]['path']).parent.glob('*.bmp'))
        for index in [0,1,len(files)-2,len(files)-1]:
            key=f'{seq}_{index:04d}';source=record(files[index])
            old=ROOT/'runs/P_s1285002/evaluations/real_step8192/motion'/seq/f'frame{index}/output_float.npz' if index<2 else None
            if old is not None:
                evidence=load(ROOT/'runs/P_s1285002/evaluations/real_step8192/verification.json')
                assert sha(old)==evidence['output_sha256'][str(old)]
            sources.append(dict(key=key,sequence=seq,index=index,source=source,reuse_output=record(old) if old is not None else None))
        pairs += [dict(sequence=seq,part='first',keys=[f'{seq}_0000',f'{seq}_0001']),dict(sequence=seq,part='last',keys=[f'{seq}_{len(files)-2:04d}',f'{seq}_{len(files)-1:04d}'])]
        if seq.startswith('20x'):
            for j,y in enumerate([1080,1390]):
                features.append(dict(kind='vertical_line_gap_profile',source_key=f'{seq}_0000',id=f'{seq}_v{j}',box=[650,y,1350,y+21],profile_axis='x'))
            raw=cv2.imread(str(files[0]),0);mask=np.zeros_like(raw);mask[540:870,100:440]=255
            pts=cv2.goodFeaturesToTrack(raw,maxCorners=16,qualityLevel=.1,minDistance=20,mask=mask,blockSize=5,useHarrisDetector=True)
            assert pts is not None and len(pts)==16
            pts=cv2.cornerSubPix(raw.astype(np.float32)/255,pts,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,50,1e-5))
            features.append(dict(kind='square_array_corners',source_key=f'{seq}_0000',id=f'{seq}_corners',points=pts.reshape(-1,2).tolist(),selection_box=[100,540,440,870]))
        if seq.startswith('50x'):
            for j,y in enumerate([450,720]):features.append(dict(kind='vertical_line_gap_profile',source_key=f'{seq}_0000',id=f'{seq}_v{j}',box=[120,y,880,y+21],profile_axis='x'))
            for j,x in enumerate([1350,1750]):features.append(dict(kind='horizontal_line_gap_profile',source_key=f'{seq}_0000',id=f'{seq}_h{j}',box=[x,1020,x+21,1410],profile_axis='y'))
    for row in load(ROOT/'analysis/structure_check/checker_features.json'):
        key=f"checker_{row['index']:04d}";sources.append(dict(key=key,sequence='checker',index=row['index'],source=record(row['path']),reuse_output=None))
        features.append(dict(kind='checker_junctions',source_key=key,id=key,points=row['corners'],selection_box=row['board_box']))
    entries=load(ROOT/'data/package/manifest.json')['entries']
    controls=[e for e in entries if e['split']=='test' and e['category'] in ['clean_identity','corners_lines_junctions','dense_close_structures']]
    assert len(controls)==58
    plan=dict(created_utc=now(),checkpoint=record(cp),sources=sources,features=features,motion_pairs=pairs,generated_controls=controls,
              questions=['Does the selected model change originally sharp known edges?','Are actual line/gap counts and corner readouts preserved?','Does source-relative motion remain consistent at the end of each acquisition?'],
              scope='Controlled-normal development diagnostics; no new training, no independent real optical truth, no unseen-holdout claim',
              fixed_definitions=dict(profile_levels=[.3,.5,.7],primary_profile_levels_from='Raw10th/90thpercentiles',sensitivity_profile_levels_from='each image10th/90thpercentiles',profile_matching='Ordered crossings only if counts and orientations agree; otherwise retain mismatch',corner_method='Raw-selected points; cornerSubPix5x5sameinitialpoints; minEigen1e-6quality flag; never remove failed points',motion='Same full-image80pixel exclusion for Raw/candidate; frozen R127reader and reversal0.1criterion',generated='Target-derived median foreground/background levels; equal-count ordered row/column crossings; report changed counts and pixel-mask topology; one view per parent',no_physical_accuracy_tolerance_invented=True),
              visual_selection='Raw-only inventory; fixed clean bar strips and square-array ROI chosen before candidate feature extraction; checker point detector chosen from Raw only',
              original_context=record(ROOT/'analysis/structure_check/raw_inventory_paths.json'),
              source_readout_code=record(ROOT/'evaluation/real.py'),preparation_source=record(__file__))
    save(out/'plan.json',plan);print(json.dumps(dict(sources=len(sources),new_inference=sum(x['reuse_output'] is None for x in sources),profiles=sum('profile' in x['kind'] for x in features),corners=sum(len(x.get('points',[])) for x in features),motion_pairs=len(pairs),known_answer_controls=len(controls))),flush=True)

if __name__=='__main__':main()
