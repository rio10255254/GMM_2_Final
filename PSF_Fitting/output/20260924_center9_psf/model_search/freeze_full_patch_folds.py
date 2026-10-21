"""Freeze complete-pillar training regions and a fresh final-view fold."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT=Path(__file__).resolve().parent
IDS=[36,35,34,30,29,28,24,23,22]
FOLDS={
 'A':dict(frames=[1,13,25],heldout_ids=[36,29,22],role='development'),
 'B':dict(frames=[4,7,12,18,23],heldout_ids=[34,30,23],role='development'),
 'C':dict(frames=[3,8,14,20,22],heldout_ids=[35,28,24],role='development_after_center_failure'),
 'D':dict(frames=[2,6,10,15,17,24],heldout_ids=[35,30,22],role='full_patch_model_selection'),
 'E':dict(frames=[5,9,11,16,19,21],heldout_ids=[34,29,24],role='frozen_final_confirmation'),
}


def main():
    all_frames=[]
    for fold,info in FOLDS.items():
        all_frames.extend(info['frames'])
        train=np.zeros((301,301),bool);hold=np.zeros_like(train)
        for i,pillar in enumerate(IDS):
            row,col=divmod(i,3);x,y=[69,150,231][col],[69,150,231][row]
            region=np.s_[y-12:y+13,x-12:x+13]
            (hold if pillar in info['heldout_ids'] else train)[region]=True
        assert train.sum()==6*625 and hold.sum()==3*625 and not np.any(train&hold)
        assert cv2.imwrite(str(ROOT/f'full_train6_{fold}.bmp'),train.astype(np.uint8)*255)
        assert cv2.imwrite(str(ROOT/f'full_hold3_{fold}.bmp'),hold.astype(np.uint8)*255)
        info['training_ids']=[p for p in IDS if p not in info['heldout_ids']]
        info['train_pixels']=int(train.sum());info['heldout_pixels']=int(hold.sum())
    assert len(all_frames)==25 and len(set(all_frames))==25
    payload={'frozen_before_full_patch_model_search':True,'observation_source':'35x35 real optical patches; score only central valid 25x25 square for each pillar',
             'SEM_shape_reference':'Original P-SEM contour at nominal 20x scale','folds':FOLDS,
             'final_fold_E_must_not_be_used_until_model_and_gates_are_locked':True}
    (ROOT/'full_patch_folds.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2))


if __name__=='__main__':main()
