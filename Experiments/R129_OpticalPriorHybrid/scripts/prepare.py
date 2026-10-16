import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import torch,numpy as np
def main():
    v42=REPO/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/V42_SoftLabelSNR_FullStandalone_20260709'
    cp=v42/'results/training_results/training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713/epoch_120.pth.tar'
    assert sha(cp)=='89942bc9b31125e836a17b6a3490d078126807e1c8bd179b73588a38c2301f83'
    old=load(R128/'trial/manifest.json')['checkpoint'];assert sha(old['path'])==old['sha256']
    s=torch.load(cp,map_location='cpu')['state_dict'];bank=s['physics_layer.PSFs'][0].numpy();candidates=s['weak_psf_block.PSFs'][0].numpy()
    assert bank.shape==(25,101,101) and candidates.shape==(4,101,101) and bank.min()>=0
    (ROOT/'data').mkdir(exist_ok=True);np.savez_compressed(ROOT/'data/measured_psf_bank.npz',mean=bank.mean(0),candidates=candidates,all_kernels=bank)
    yy,xx=np.mgrid[:101,:101];centroids=[[(k*xx).sum()/k.sum()-50,(k*yy).sum()/k.sum()-50] for k in bank]
    oldscale=float(s['weak_psf_block.beta_scale']);oldbeta=float(s['weak_psf_block.beta'])
    save(ROOT/'data/PSF_PROVENANCE.json',dict(source_checkpoint=record(cp),source_model=record(v42/'model_v42.py'),source_state_key='state_dict',only_calibration_buffers_transferred=True,learned_V42_weights_transferred=False,
        kernel_shape=list(bank.shape),candidate_shape=list(candidates.shape),centroid_offsets_xy=centroids,stored_adaptive_beta=oldbeta,stored_adaptive_beta_scale=oldscale,stored_effective_adaptive_strength=oldbeta*oldscale,
        current_origin='Measured kernels unchanged; Fourierphase defines intensitycentroid as origin in the new operator. This is an explicit new convention,not exactlegacyFFTcode.',
        independent_physical_calibration_qualified=False,calibration_vs_training='Prior may derive from oldSEM-basedcalibration; real/SEM image targets are not introduced. Do not claimfullyindependentSEMconfirmation.',bank=record(ROOT/'data/measured_psf_bank.npz')))
    source=load(R128/'results/lsc_comparison/plan.json');pairs=[]
    import pandas as pd
    table=pd.read_csv(R128/'results/lsc_comparison/locked_pairs.csv')
    for seq,g in table.groupby('sequence',sort=False):
        first=g.sort_values('start_frame_index').iloc[0];pairs.append(dict(sequence=seq,start=int(first.start_frame_index),end=int(first.end_frame_index)))
    plan=dict(created_utc=now(),source_checkpoint=old,calibration=record(ROOT/'data/measured_psf_bank.npz'),provenance=record(ROOT/'data/PSF_PROVENANCE.json'),shared_data=record(R128/'data/package/manifest.json'),
        purpose='Honor requested thesis design requirements while measuringactualbenefitsandcosts.',
        requirements=['active measuredPSFmean/adaptivefusion','V42-styleAAupsampling','input-referenced high-frequency anchor andboundedqualityadjustment'],
        implementation_differences=['nativeimage opticalstage evaluatedonceperinput,notlegacyfeaturelayer','correctedFFToriginandunitDCgain,reg.0565fromexistingWiener calibration','newcommonbilinearconvdecoderheadinitializesfrommeanofR128fourphaseheads','qualitystatisticssimplifiedandexplicit;notcalibratedconfidence','rawanchorqualitysharedacrossallpilotarms,not independentlyattributed'],
        arms={'A':dict(optical=False,aa=False),'B':dict(optical=True,aa=False),'C':dict(optical=False,aa=True),'D':dict(optical=True,aa=True)},primary_candidate='D',
        common_seed=1295001,updates_per_arm=24,train_indices=list(range(24)),dev_indices=list(range(8)),learning_rate=1e-5,optimizer='AdamW',weight_decay=1e-5,loss_weights=dict(image=1.,gradient=.2,pair=.2),
        training_scope='MatchedshortfinetuningofcommonconvertedR128parent,notfullfromscratchtraining. Sameexistingproceduralsourcepairs; fixedmeasuredbankisaprior,notthescene-specifictruePSF.',
        real_normal_exposures=[13,14,15],motion_pairs=pairs,motion_scope='FixedRaw-derivednine-pillarROIs with160pxcontext; ROIconditionedpilot,notfullFOVthesis120-pair result.',
        limits=['one seed/24stepsonly;notconvergedcapability','oldmeasuredpriornotindependentSEMqualification','no oldconfirmationaccess','fullV42moduleequivalence notclaimed','no causalclaimforcommonhead/anchorfrom2x2factors'],storage_budget_gib=4,model_code=record(ROOT/'model/hybrid.py'))
    save(ROOT/'config/plan.json',plan)
    save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='preparing',kind='bounded_integration_pilot',model='R129_OpticalPriorHybrid',expected_updates=96,new_training_updates=0,created_utc=now()))
    print('Frozen:25measuredkernels,4candidates;oldadaptiveeffectivegain=',oldbeta*oldscale)
if __name__=='__main__':main()
