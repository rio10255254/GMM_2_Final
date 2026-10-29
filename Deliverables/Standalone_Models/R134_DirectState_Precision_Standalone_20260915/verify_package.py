from runtime import *
def verify(full=True):
    manifest=load(ROOT/'PACKAGE_MANIFEST.json');checked=0
    for rel,expected in manifest['files'].items():
        p=ROOT/rel
        if not full and rel.startswith('training_data/'):continue
        if not p.is_file() or sha(p)!=expected:raise RuntimeError('Package source changed: '+rel)
        checked+=1
    cfg=load(ROOT/'config/training.json');entries=load(ROOT/'training_data/manifest.json')['entries'];assert len(entries)==sum(cfg['splits'].values());seen=set();geometry={s:set() for s in cfg['splits']}
    for e in entries:
        key=e['split'],e['index'];assert key not in seen;seen.add(key);geometry[e['split']].add(e['geometry_sha256'])
        if full:
            m=load(ROOT/'training_data'/e['metadata_path']);assert not m['external_source_inputs'] and not m['real_or_SEM_answers_used']
    assert not (geometry['train']&geometry['dev'] or geometry['train']&geometry['test'] or geometry['dev']&geometry['test'])
    return dict(passed=True,files_checked=checked,parents=len(entries),generation=manifest['generation'])
if __name__=='__main__':print(verify(True))
