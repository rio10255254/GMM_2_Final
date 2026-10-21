"""Repair only coverage quantization; preserve existing source/target/SDF arrays.

The first payload used OpenCV uint8 area rounding for coverage. The original
reference uses float coverage followed by NumPy rounding. Coverage is not used
by the current objective; store a versioned corrected sidecar for future use.
"""
from pathlib import Path
import json
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.build_sequences import geometry,poses,sha,BASE
from data.geometry import translate_high


def main():
    cv2.setNumThreads(1)
    records={r['scene_index']:r for r in json.loads((BASE/'manifest.json').read_text())['records']}
    report=[]
    for split in ['train','validation']:
        folder=ROOT/'data/sequences'/split
        manifest=json.loads((folder/'manifest.json').read_text())
        out=folder/'coverage_v2';out.mkdir(exist_ok=False)
        for row in manifest['records']:
            record=records[row['scene_index']];mask,_=geometry(record)
            coverage=mask.astype(np.float32)/255
            fixed=[]
            for dx,dy in poses():
                shifted=translate_high(coverage,dx,dy,8,cv2.INTER_LINEAR)
                fixed.append(np.rint(cv2.resize(shifted,(256,256),interpolation=cv2.INTER_AREA)*255).astype(np.uint8))
            fixed=np.stack(fixed)
            assert np.array_equal(fixed[0],np.load(BASE/record['mask_a']))
            path=out/row['file'];np.savez_compressed(path,mask=fixed)
            with np.load(folder/row['file']) as old:
                delta=np.abs(fixed.astype(np.int16)-old['mask'].astype(np.int16))
                maxdiff=int(delta.max());changed=int((delta>0).sum())
            report.append({'split':split,'scene_index':row['scene_index'],'path':str(path.relative_to(ROOT)),
                'sha256':sha(path),'changed_coverage_pixels':changed,'max_difference_gray':maxdiff})
            assert sha(folder/row['file'])==row['sha256']
    with (ROOT/'results/coverage_repair.json').open('x') as stream:
        json.dump({'status':'pass','only_coverage_sidecars_changed':True,'original_payload_unchanged':True,
                   'coverage_unused_by_current_objective':True,'records':report},stream,indent=2)
    print(json.dumps({'status':'pass','scenes':len(report),'max_delta':max(r['max_difference_gray'] for r in report),
                      'new_bytes':sum((ROOT/r['path']).stat().st_size for r in report)}))


if __name__=='__main__':main()
