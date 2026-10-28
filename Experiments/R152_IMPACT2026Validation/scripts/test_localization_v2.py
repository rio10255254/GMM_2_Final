from pathlib import Path
import json,pandas as pd
from test_localization_candidates import run
from validate_localization_real_shifts import main as real_check
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/localization_improvement'
def main():
    frames=[]
    for split in ['development','heldout']:
        df=run(split,extended=True);df.to_csv(OUT/f'synthetic_{split}_v2.csv',index=False);frames.append(df)
    summary=pd.concat(frames).groupby(['split','reader','mag']).vector_error_px.agg(['mean','median','max']).reset_index();summary.to_csv(OUT/'synthetic_summary_v2.csv',index=False)
    print(summary.to_string(index=False),flush=True);real_check(extended=True)
    dev=pd.read_csv(OUT/'real_content_known_shifts_v2.csv');table=dev.groupby(['reader','method']).vector_error_px.mean().unstack()
    baseline=table.loc['fixed_state_lsc'];eligible=table.index[(table<=baseline*1.001).all(axis=1)].tolist();eligible=[r for r in eligible if r!='fixed_state_lsc']
    if not eligible:raise RuntimeError('No candidate improves all three methods on known shifts')
    selected=table.loc[eligible].mean(axis=1).idxmin()
    lock=dict(selected_reader=selected,selection='Known-shift development only: lower mean vector error than fixed-state LSC for Raw, Wiener and R152; minimize balanced mean among eligible readers',real120_scores_used=False,eligible=eligible,mean_known_shift_errors_px=table.to_dict(),initial_candidate_rejected='radial_intensity_fit increased known-shift error on R152',background_plane_reason='Original pair fit did not absorb illumination-plane change; adding photometric nuisance terms is justified by known-shift errors, without real nominal-step scores',requires_fresh_validation=True)
    (OUT/'final_reader_lock.json').write_text(json.dumps(lock,indent=2)+'\n');print('FINAL LOCK',json.dumps(lock,indent=2),flush=True)
if __name__=='__main__':main()
