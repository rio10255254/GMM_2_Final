"""Re-run existing native SEM/optical scale checks into new paths, not new qualification."""
from pathlib import Path
import sys,ast
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *

def main():
    source=ROOT.parent/'R127_MeasurementPreservationRepair/scripts/sem_native_audit_v2.py';previous=load(ROOT.parent/'R127_MeasurementPreservationRepair/results/sem_native_v2/summary.json')
    for r in previous['sources']:assert sha(r['path'])==r['sha256'],r['path']
    tree=ast.parse(source.read_text(encoding='utf-8-sig'));nodes=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='common') and not isinstance(n,ast.If)]
    scope=dict(ROOT=ROOT,EXPS=ROOT.parent,Path=Path,np=np,json=json,record=record,save=save,__name__='r134_native_calibration_replay')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope);scope['main']()
    current=load(ROOT/'results/sem_native_v2/summary.json');keys=['optical_pitch','native_SEM_pitch_median','native_SEM_to_optical_scale','relative_factor_to_historical','median_SEM_edge_definition_width_optical_px']
    errors={k:abs(current[k]-previous[k]) for k in keys};assert max(errors.values())<1e-7
    for r in previous['sources']:assert sha(r['path'])==r['sha256']
    save(ROOT/'results/native_calibration_replay.json',dict(source=record(source),recomputed_from_original_images=True,comparison_errors=errors,old_sources_unchanged=True,does_not_establish_new_sample_or_material_edge_qualification=True,physical_boundary_definition_still_required=True));print('Native original-image calibration replay passed',flush=True)
if __name__=='__main__':main()
