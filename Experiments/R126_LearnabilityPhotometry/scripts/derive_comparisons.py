"""Pillar-paired treatment differences and complete failure counts, not selection."""
import pandas as pd
from common import *

def main():
    root=ROOT/'results/real_comparison';data=pd.read_csv(root/'all8_common_sem_per_pillar.csv');last=data[data.step==128];paired=[]
    for (ref,exp,seed),d in last.groupby(['reference','exposure','seed']):
        p=d[d.arm=='P'].set_index('pillar');q=d[d.arm=='Q'].set_index('pillar');assert p.index.equals(q.index) and len(p)==36
        difference=q.common_mae_px-p.common_mae_px
        paired.append(dict(reference=ref,exposure=int(exp),seed=int(seed),physical_objects=36,P_median_change_vs_Raw_px=float(p.common_mae_change_vs_Raw_px.median()),Q_median_change_vs_Raw_px=float(q.common_mae_change_vs_Raw_px.median()),median_pillar_Q_minus_P_px=float(difference.median()),Q_better_pillars=int((difference<0).sum()),Q_worse_pillars=int((difference>0).sum()),Q_worse_than_Raw_pillars=int((q.common_mae_change_vs_Raw_px>0).sum()),P_worst_pillar_mae=float(p.common_mae_px.max()),Q_worst_pillar_mae=float(q.common_mae_px.max())))
    pd.DataFrame(paired).to_csv(ROOT/'results/photometry_paired_comparison.csv',index=False)
    motion=pd.read_csv(root/'motion_comparison.csv');final=motion[motion.step==128];m=[]
    for (arm,seed),d in final.groupby(['arm','seed']):
        m.append(dict(arm=arm,seed=int(seed),pairs=len(d),low_response_pairs=int((~d.candidate_response_at_least0p1).sum()),maximum_change_vs_Raw_px=float(d.candidate_minus_Raw_vector_px.max()),maximum_change_vs_own_initial_px=float(d.change_from_own_step0_vector_px.max())))
    result=dict(SEM_treatment_comparison=paired,motion_final=m,SEM_population='Same Raw/all8 shared normals,36reused pillars per reference/exposure, no independent specimen count inflation',motion_scope='Six reused pairs, no independently known actual stage motion',reference_table_sha256=sha(root/'all8_common_sem_per_pillar.csv'),model_adopted=False,calibration_qualified=False)
    save(ROOT/'results/derived_comparisons.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
