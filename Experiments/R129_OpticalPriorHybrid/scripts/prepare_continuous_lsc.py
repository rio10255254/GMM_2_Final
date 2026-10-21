"""Freeze all201 frames, historical120 pairs and source-defined session boundaries."""
import sys,re,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continuous_common import *
import cv2
def main():
    oldpath=REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/plan.json';old=load(oldpath);cfg=load(old['configuration']['path']);sessions=pd.read_csv(old['sessions']['path']);frames=[];adjacent=[]
    for sequence,s in cfg['sequences'].items():
        paths=sorted(Path(s['raw_dir']).glob('frame_*.bmp'));previous=None
        for path in paths:
            index=int(path.stem.split('_')[-1]);rows=sessions[(sessions.sequence==sequence)&(sessions.start_frame_index<=index)&(sessions.end_frame_index>=index)];assert len(rows)==1 and bool(rows.iloc[0].anchor_success)
            session=int(rows.iloc[0].session_id);shape=list(cv2.imread(str(path),0).shape);assert shape==[1536,2048]
            frames.append(dict(sequence=sequence,frame_index=index,session=session,source=record(path),shape=shape))
            if previous:
                assert index==previous[0]+1
                adjacent.append(dict(sequence=sequence,magnification=s['magnification'],pair_rank_raw_locked=index,start_frame_index=previous[0],end_frame_index=index,session_start=previous[1],session_end=session,is_repositioning=previous[1]!=session))
            previous=(index,session)
    assert len(frames)==201 and len(adjacent)==197 and sum(x['is_repositioning'] for x in adjacent)==3
    pairs=REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/locked_pairs.csv';fixed=pd.read_csv(pairs)
    keys={(x['sequence'],x['start_frame_index'],x['end_frame_index']) for x in adjacent if not x['is_repositioning']}
    assert len(fixed)==120 and all((r.sequence,r.start_frame_index,r.end_frame_index) in keys for r in fixed.itertuples())
    pd.DataFrame(adjacent).to_csv(OUT/'all_adjacent_pairs.csv',index=False)
    pkg=Path(load(ROOT/'config/standalone_build.json')['path']);cp=pkg/'results/training/r129_long_01/checkpoints/step08192.pth'
    sources=[record(oldpath),old['configuration'],old['sessions'],record(pairs),record(ROOT/'scripts/sequence_inference.py'),record(ROOT/'scripts/continuous_common.py'),record(REPO/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py')]
    sources += [x for x in old['sources'] if any(n in x['path'] for n in ['reference_circle_core.py','run_displacement_lsc.py','run_lsc_e42.py'])]
    for method in ['Raw','R128_P_s1285002','R61v16_PSFOFF']:
        base=REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/measurements'/method
        sources += [record(base/name) for name in ['centers.csv','per_pair.csv','summary.csv']]
    save(OUT/'plan.json',dict(created_utc=now(),source=record(__file__),checkpoint=record(cp),package=str(pkg),frames=frames,configuration=old['configuration'],sessions=old['sessions'],locked_pairs=record(pairs),adjacent_pairs=record(OUT/'all_adjacent_pairs.csv'),protected_sources=sources,primary='Same120 pre-existing Raw-selected pairs asR128/R61; no reselection',secondary='All194 within-session adjacent pairs, Raw andR129; all3repositioning transitions retained separately',inference='Full native2048x1536; global optics/features/state/quality/anchor; finite-support prior tiles core512/halo16',boundary_rule='OriginalR129Rawretentionthrough80/transition16; R128has64/16, so compare operational models and report shared fully-neural context separately',reader='Unchanged R128/R61 reader, reset curvature per pillar; 64points20x/96points50x, iterations13/15, normalhalfwidth2.4/4',scopes=['No training or parameter edits','Old real development sequences, not unseen confirmation','Commanded displacement is not independently measured true position','No old144confirmationpayloadaccess'],budget_gib=6))
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';d=load(reg);save(OUT/'storage_before.json',d)
    item=next(x for x in d['entries'] if x.get('id')=='r129_optical_prior_hybrid');item.update(budget_gib=6,state='continuous_lsc_validation_running');item['keep']+=' Continuous201fullframes plus exactreader centers/points, fixed120 andwithin-session194 pairs; preserve failures and all original data.'
    reg.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Fixed201frames,120comparisonpairs,194within-sessionpairs and3repositioning transitions')
if __name__=='__main__':main()
