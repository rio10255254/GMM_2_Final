import sys,ast,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,sha
R=ROOT.parents[1];old=R/'Experiments/R136_PIRepeatability';hand=R/'Deliverables/Thesis_Handoffs/R129_Corrected_Corner9_Thesis_Handoff_20260920'
def main():
 protected=[];copies=[]
 def copy(src,rel):
  dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);h=sha(src);assert sha(dest)==h
  protected.append(dict(path=str(src),sha256=h));copies.append(dict(source=str(src),copy=str(dest.relative_to(ROOT)),sha256=h))
 plan=load(old/'config/plan.json');save(ROOT/'evaluation/capture_plan.json',dict(runs=plan['runs'],frames=plan['frames']))
 copy(old/'config/sem_corner9_lsc_plan.json','evaluation/measurement_config.json')
 copy(old/'results/sem_corner9/tracking.csv','evaluation/tracking.csv')
 copy(old/'results/sem_corner9/R129_revalidation_20260920/analysis/tables/calibration.json','evaluation/calibration.json')
 copy(old/'results/sem_corner9/sem_mapping_candidates.json','evaluation/sem_mapping_candidates.json')
 copy(R/'Experiments/R135_UnifiedModelComparison/results/Raw/sem/points.npz','evaluation/sem_points.npz')
 copy(R/'Experiments/R135_UnifiedModelComparison/results/Raw/sem/complete.json','evaluation/sem_scale.json')
 for model in ['Raw','R129']:
  for p in sorted((hand/'04_Verification_and_Sources/centers'/model).glob('*')):
   if p.is_file() and p.suffix in ['.npz','.csv']:copy(p,'evaluation/baseline_centers/'+model+'/'+p.name)
 for name in ['main_comparison.csv','all_displacements_3600.csv','SEM_group_mean_size.csv','SEM_direction_sensitivity.csv']:
  copy(hand/'01_Raw_R129_Comparison'/name,'evaluation/baseline_reference/'+name)
 copy(old/'config/plan.json','config/original_capture_plan.json')
 copy(old/'scripts/lsc_core.py','config/original_measurement_interface.py.txt')
 source=(old/'scripts/lsc_core.py').read_text(encoding='utf-8');tree=ast.parse(source)
 functions=[ast.get_source_segment(source,x) for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['reset_curvature','measure_image']]
 assert len(functions)==2
 body='import numpy as np\nimport skimage.segmentation.morphsnakes as morphsnakes\nfrom evaluation import reference_circle_core as core\n\n'+'\n\n'.join(functions)+'\n'
 (ROOT/'evaluation/measurement_interface.py').write_text(body,encoding='utf-8')
 core=ROOT/'evaluation/reference_circle_core.py';assert sha(core)==load(ROOT/'evaluation/measurement_config.json')['core_source']['sha256']
 protected.append(dict(path=str(R/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py'),sha256=sha(core)))
 # Preservation audit concerns old results/code; never deserialize an old model.
 for item in load(hand/'MANIFEST.json'):
  p=hand/item['path'];assert sha(p)==item['sha256'];protected.append(dict(path=str(p),sha256=item['sha256']))
 for p in (R/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912/model').glob('*.py'):protected.append(dict(path=str(p),sha256=sha(p)))
 unique=list({p['path']:p for p in protected}.values());save(ROOT/'config/protected_sources.json',unique)
 save(ROOT/'config/evaluation_manifest.json',dict(copies=copies,local_files={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'evaluation').rglob('*') if p.is_file()},measurement_functions_exact_source=True,no_old_weights_loaded=True,no_real_model_evaluation_performed=True))
 print('Frozen evaluation interface and baseline inputs prepared; no real inference performed.',flush=True)
if __name__=='__main__':main()
