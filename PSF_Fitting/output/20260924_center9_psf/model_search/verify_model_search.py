"""Verify sealed full-patch comparisons and the 25-kernel research bank."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


ROOT=Path(__file__).resolve().parent
RUN=ROOT.parent


def load_json(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    frozen=load_json(ROOT/'full_patch_folds.json')
    selected=load_json(ROOT/'selected_full_patch_before_E.json')
    assert frozen['frozen_before_full_patch_model_search'] and selected['selection_frozen_before_E']
    assert frozen['final_fold_E_must_not_be_used_until_model_and_gates_are_locked']
    assert selected['frozen_final_fold']=={
        'frames':frozen['folds']['E']['frames'],
        'heldout_sem_ids':frozen['folds']['E']['heldout_ids']}
    all_frames=sum([r['frames'] for r in frozen['folds'].values()],[])
    assert len(all_frames)==len(set(all_frames))==25
    assert len(rows(ROOT/'full_patch_screen_metrics.csv'))==19*4
    assert all(r['fold']!='E' for r in rows(ROOT/'full_patch_screen_metrics.csv'))
    center_reassessment=load_json(ROOT/'C_full_patch_reassessment.json')
    assert center_reassessment['status']=='FAIL_full_patch_even_though_frozen_center_gates_passed'

    development=rows(ROOT/'full_BADS_development_metrics.csv')
    assert len(development)==19
    assert all(float(r['heldout_mse'])<float(r['gaussian_heldout_mse']) for r in development)
    assert all(int(r['exitflag'])>0 and float(r['peak_offset_px'])==0 for r in development)
    assert max(abs(float(r['heldout_mse'])-float(r['differential_evolution_heldout_mse'])) for r in development)<2e-6
    verdict=load_json(ROOT/'E_full_patch_verdict.json')
    assert verdict['status']=='PASS_predictive_research_PSF' and all(verdict['gates'].values())
    assert verdict['frames']==frozen['folds']['E']['frames']
    assert len(rows(ROOT/'E_full_patch_metrics.csv'))==6*4
    per=rows(ROOT/'E_full_patch_per_pillar.csv')
    assert len(per)==6*3*4
    scores={(int(r['frame']),int(r['sem_id']),r['model']):float(r['full_patch_mse']) for r in per}
    pairs={(frame,pillar) for frame,pillar,_ in scores}
    assert len(pairs)==18
    mix_better_gaussian=sum(scores[(f,p,'selected_core_halo_BADs')]<scores[(f,p,'gaussian')] for f,p in pairs)
    mix_better_original=sum(scores[(f,p,'selected_core_halo_BADs')]<scores[(f,p,'original_disk_BADs')] for f,p in pairs)
    assert mix_better_gaussian==mix_better_original==18

    full=load_json(ROOT/'full25_core_halo_summary.json')
    assert full['status']=='research_candidate_not_formal_baseline' and full['source_acquisition_frames']==25
    assert full['all_25_BADs_exitflags_positive'] and full['all_25_peaks_centered']
    assert full['max_centroid_offset_px']<1e-10 and full['max_outer_3px_energy_fraction']<.001
    assert len(rows(ROOT/'mixture_full_ALL'/'batch_results.csv'))==25
    bank=loadmat(ROOT/'PSF_20260924_SEM_core_halo_25_RESEARCH.mat')
    psfs=bank['psf_grid']
    assert psfs.shape==(101,101,5,5)
    assert np.isfinite(psfs).all() and (psfs>=0).all()
    assert np.allclose(psfs.sum(axis=(0,1)),1,atol=1e-10)
    assert bank['research_only'].item()==1
    assert np.array_equal(bank['sem_ids_image_rows'],np.array([[36,35,34],[30,29,28],[24,23,22]]))
    assert (ROOT/'E_frame16_full_patch.png').is_file()
    assert (ROOT/'full_patch_validation_summary.png').is_file()
    assert (ROOT/'PSF_core_halo_25_grid.png').is_file()
    assert (ROOT/'README_TW.md').is_file()

    manifest=rows(ROOT/'source_sha256.csv')
    assert len(manifest)==9
    for record in manifest:
        p=Path(record['absolute_path'])
        assert p.is_file() and p.stat().st_size==int(record['bytes']) and sha(p)==record['sha256']
    report={'status':'PASS',
            'distinct_views_in_frozen_full_patch_folds':25,
            'development_views_where_mixture_beats_gaussian':19,
            'frozen_E_views_where_mixture_beats_gaussian':6,
            'frozen_E_pillar_appearances_where_mixture_beats_gaussian':mix_better_gaussian,
            'frozen_E_pillar_appearances_where_mixture_beats_original_BADs':mix_better_original,
            'research_PSF_kernels':25,'source_hashes_verified':len(manifest),
            'accepted_PSF_replaced':False,
            'independent_specimen_PSF_trueness_proved':False}
    (ROOT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
