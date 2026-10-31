"""Phase 4 hand fix, found on 2026-10-31: prose that named a folder inside its own package.

Two documents wrote `Traing_Progress/...` meaning a `Traing_Progress` folder of their own, not the one at
the project root: a copy of Model/README.md inside the R26 package backup (the package has its own
`內部檔案/Traing_Progress/`), and a LabSystem R62 report naming LabSystem's own training runs
(`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_*`, which the root never held). The move rule
rewrote them to Experiments/Legacy and Experiments/Training_Runs. Those lines go back to the text they had
before the restructure, and the new sha256 of each file is carried into the records that hold it.
Rerunning changes nothing.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'Tools'))
from restructure_hashes import propagate  # noqa: E402
from restructure_tree import rewritable, tracked  # noqa: E402
import restructure_verify as verify  # noqa: E402

BASE = '20b0d56d62a8c70854ffb11b396d171110d0d9e4'   # main just before phase 1
R26 = 'Experiments/R26NewPSFCheck/artifacts/package_mainline_realign_20260326_234441/backups/內部檔案/Model/README.md'
R62 = 'Experiments/R62_TargetSampleBoost/reports/R62_SELFSHIFT_TRAINING_DECISION_20260705.md'
FIXES = [(R26, R26, (41, 51)),
         ('LabSystem_MOSR/' + R62, 'Thesis_MOSR_Evidence/LabSystem_MOSR/' + R62, (65, 86))]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    seeds, sizes = {}, {}
    for now_path, base_path, lines in FIXES:
        p = REPO / now_path
        data = p.read_bytes()
        base = subprocess.run(['git', '-C', str(REPO), 'show', f'{BASE}:{base_path}'],
                              capture_output=True, check=True).stdout.decode('utf-8').split('\n')
        cur = data.decode('utf-8').split('\n')
        for n in lines:
            if cur[n - 1] == base[n - 1]:
                continue
            assert 'Traing_Progress/' in base[n - 1] and 'Traing_Progress' not in cur[n - 1], (now_path, n)
            cur[n - 1] = base[n - 1]
        new = '\n'.join(cur).encode('utf-8')
        if new != data:
            p.write_bytes(new)
            seeds[sha(data)] = sha(new)
            sizes[sha(new)] = len(new)
            print('restored', now_path, lines)
    if not seeds:
        print('nothing to do')
        return
    names = [n for n in tracked(REPO) if rewritable(n) and not verify.is_record(n) and (REPO / n).exists()]
    rep = propagate(seeds, sizes, names, lambda n: (REPO / n).read_bytes(), lambda n, d: (REPO / n).write_bytes(d))
    for n in rep.touched_files:
        d = (REPO / n).read_bytes()
        sizes[sha(d)] = len(d)
    print('records updated:', *sorted(rep.touched_files), sep='\n  ')
    path = REPO / 'docs/operations/TREE_RESTRUCTURE_20261028/hash_changes_phase4.json'
    saved = json.loads(path.read_text(encoding='utf-8'))
    final = {}
    for k, v in saved['changes'].items():
        while v in rep.changes:
            v = rep.changes[v]
        final[k] = v
    for k, v in rep.changes.items():
        if k not in saved['changes'].values() and k not in final:
            while v in rep.changes:
                v = rep.changes[v]
            final[k] = v
    sizes_all = dict(saved.get('bytes', {}))
    for k, v in final.items():
        if v in sizes:
            sizes_all[k] = sizes[v]
    path.write_text(json.dumps({'changes': final, 'bytes': sizes_all, 'rounds': saved.get('rounds', 0) + rep.rounds},
                               indent=1) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
