"""Correct the ordering-only improved-count summary without rerunning inference."""
from pathlib import Path
import json,os
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/training_deep_dive';path=OUT/'frozen_checkpoint_audit.json';result=json.loads(path.read_text(encoding='utf-8'));stages=pd.read_csv(OUT/'frozen_stage_audit.csv');summary=[]
for stage,g in stages.groupby('stage'):
 g=g.sort_values('index');previous=None if stage==0 else stages[stages.stage==stage-1].sort_values('index')
 summary.append(dict(stage=int(stage),samples=len(g),combined_score=float(g.combined_score.mean()),image=float(g.image.mean()),gradient=float(g.gradient.mean()),pair_output=float(g.pair_output.mean()),boundary=float(g.boundary.mean()),increment_RMS_gray=float(g.increment_RMS_gray.mean()),total_residual_RMS_gray=float(g.total_residual_RMS_gray.mean()),improved_vs_previous=None if stage==0 else int((g.combined_score.to_numpy()<previous.combined_score.to_numpy()).sum())))
result['stage_summary']=summary;result['correction_note']='Initial improved-count summary compared unsorted current rows with sorted previous rows. Per-row values were correct; counts were recomputed by index without rerunning inference.';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path);print(json.dumps(summary,indent=2))
