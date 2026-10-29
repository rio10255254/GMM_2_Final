"""Verify portable resources and source lineage; this does not certify efficacy."""
import argparse,collections
from runtime import *
def verify(full=True):
    manifest=load(ROOT/'PACKAGE_MANIFEST.json');checked=0
    for name,expected in manifest['files'].items():
        if not full and name.startswith('training_data/') and name!='training_data/manifest.json':continue
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():raise RuntimeError('Missing package file: '+name)
        if sha(path)!=expected:raise RuntimeError('Package file mismatch: '+name)
        checked+=1
    entries=load(ROOT/'training_data/manifest.json')['entries'];cfg=load(ROOT/'config/training.json')
    counts=collections.Counter(e['split'] for e in entries)
    if dict(counts)!=cfg['splits']:raise RuntimeError('Split counts differ')
    geometry={s:set() for s in counts};categories=collections.Counter()
    for e in entries:
        geometry[e['split']].add(e['geometry_sha256']);categories[(e['split'],e['category'])]+=1
        if full:
            m=load(ROOT/'training_data'/e['metadata_path'])
            if m['external_source_inputs'] or m['real_or_SEM_answers_used']:raise RuntimeError('Non-source-only training record')
            if m['parent_id']!=e['parent_id'] or m['geometry_sha256']!=e['geometry_sha256']:raise RuntimeError('Lineage mismatch')
            if sha(ROOT/'training_data'/e['arrays_path'])!=e['arrays_sha256']:raise RuntimeError('Original arrays changed')
            if sha(ROOT/'training_data'/e['metadata_path'])!=e['metadata_sha256']:raise RuntimeError('Original metadata changed')
    for a in geometry:
        for b in geometry:
            if a!=b and geometry[a]&geometry[b]:raise RuntimeError('Geometry overlaps between splits')
    if full:
        # Paths in history/provenance are intentionally retained; executable code is local.
        import re
        for p in [*ROOT.glob('*.py'),*ROOT.glob('model/*.py'),*ROOT.glob('validation/*.py'),*ROOT.glob('validation/*.m')]:
            text=p.read_text(encoding='utf-8-sig')
            if re.search(r'[A-Za-z]:[\\/].*(GMM|Thesis_MOSR|Experiments)',text):raise RuntimeError('Original workspace path in executable: '+p.name)
    result=dict(passed=True,files_checked=checked,full=full,splits=dict(counts),cross_split_geometry_overlap=0,categories={f'{s}/{c}':n for (s,c),n in categories.items()},independent_runtime_paths=True,scientific_qualification=False)
    print('Package verification:',checked,'files; splits',dict(counts),flush=True);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');a=p.parse_args();verify(not a.quick)
