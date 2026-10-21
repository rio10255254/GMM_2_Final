"""Recalculate key LSC numbers from saved displacement rows using Python3 only."""
from pathlib import Path
import csv,statistics,collections
root=Path(__file__).resolve().parent/'02_統計表/CSV'
def read(name):
    with (root/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
groups=collections.defaultdict(list)
for r in read('all_measurements.csv'):groups[(r['view'],r['kind'],r['model'])].append(r)
count=0
for expected in read('readable_lsc_summary.csv'):
    key=(expected['view'],expected['kind'],expected['model']);rows=groups[key];e=[float(r['error_nm']) for r in rows];positions=collections.defaultdict(list)
    for r in rows:positions[r['j']].append(float(r['error_nm']))
    found={'mae_nm':statistics.mean(abs(x) for x in e),'bias_nm':statistics.mean(e),'maximum_error_nm':max(abs(x) for x in e),'repeatability_nm':statistics.mean(statistics.stdev(v) for v in positions.values())}
    for k,v in found.items():assert abs(v-float(expected[k]))<1e-5,(key,k,v,expected[k]);count+=1
print('Recomputed and matched',count,'key statistics without the original computer or GPU.')
