from r135_common import *
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    plan=load(ROOT/'config/plan.json');files=set()
    for tag,info in plan['models'].items():
        if tag=='V42_old':folders=[Path(PROJECT_ROOT / info['inference']).parent]
        elif tag=='R61':folders=[Path(PROJECT_ROOT / info['command'][1]).parent]
        elif tag=='V42_clean':folders=[REPO/'Experiments/R130_CleanV42Comparison/model',REPO/'Experiments/R130_CleanV42Comparison/scripts',REPO/'Experiments/R130_CleanV42Comparison/calibration',REPO/'Experiments/R130_CleanV42Comparison/config']
        elif tag=='R128':folders=[REPO/'Experiments/R128_SourceOnlyFullTraining/model',REPO/'Experiments/R124_RealFirstPrototype/inference']
        else:folders=[Path(PROJECT_ROOT / info['package'])] if tag=='R134_P1' else [REPO/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912']
        for directory in folders:
            for p in directory.glob('*.py'):files.add(p)
            for p in directory.glob('*.json'):files.add(p)
            if (directory/'PACKAGE_MANIFEST.json').exists():
                manifest=load(directory/'PACKAGE_MANIFEST.json')
                if 'files' not in manifest:
                    assert manifest.get('package_name')=='V42_SoftLabelSNR_FullStandalone_20260709' and 'main_files' in manifest
                    for rel in manifest['main_files'].values():assert (directory/rel).is_file()
                    # This legacy catalog never contained content hashes. Check its
                    # model/checkpoint against the previously recorded R130 provenance.
                    for item in load(REPO/'Experiments/R130_CleanV42Comparison/config/provenance.json')['protected']:
                        if Path(PROJECT_ROOT / item['path']).resolve().is_relative_to(directory.resolve()):assert sha(str(PROJECT_ROOT / item['path']))==item['sha256']
                for rel,h in manifest.get('files',{}).items():
                    if rel.endswith(('.py','.m')) or rel.startswith(('config/','calibration/','weights/')):assert sha(directory/rel)==h;files.add(directory/rel)
        if tag=='V42_clean':
            for r in load(REPO/'Experiments/R130_CleanV42Comparison/config/frozen.json')['sources']:assert sha(str(PROJECT_ROOT / r['path']))==r['sha256'];files.add(Path(PROJECT_ROOT / r['path']))
    files.add(P134.parent/'tiled.py');save(ROOT/'config/dependencies.json',dict(utc=now(),scope='Current runtime dependencies recorded before remaining model runs; native oldV42 model/checkpoint were already protected in the plan',sources=[record(p) for p in sorted(files)]));print('Dependencies verified',len(files))
if __name__=='__main__':main()
