from pathlib import Path
import json,zipfile,shutil,html
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results/shape_size'; REPO=ROOT.parents[1]
s=pd.read_csv(OUT/'summary.csv'); rows=pd.read_csv(OUT/'per_contour.csv')
for r in s.itertuples():
    d=rows[rows.model==r.model]
    assert len(d)==8370 and d.run.nunique()==30
    sd=np.sqrt(d.groupby(['index','pillar_id']).diameter_nm.var(ddof=1).mean())
    assert abs(sd-r.diameter_repeat_sd_nm)<1e-9
    p=np.load(OUT/f'{r.model}_radial_profiles.npz')['radius_nm'].astype(float)
    p-=p.mean(axis=-1,keepdims=True)
    assert abs(np.sqrt(p.var(axis=0,ddof=1).mean())-r.shape_repeat_sd_nm)<1e-4

table='| 組別 | 平均直徑 μm | 尺寸重拍波動 nm | 形狀重拍波動 nm | 最大全次尺寸偏離 nm |\n|---|---:|---:|---:|---:|\n'
for r in s.itertuples():table+=f'| {r.model} | {r.diameter_mean_nm/1000:.4f} | {r.diameter_repeat_sd_nm:.2f} | {r.shape_repeat_sd_nm:.2f} | {r.diameter_repeat_absmax_nm:.2f} |\n'
text='''# R136 四組輪廓、形狀與尺寸驗證：重拍部分

2026-09-19。已完成現有 30 次重拍的比較；使用者確認另有同批實物參考，等待提供位置。準確程度的驗證尚未完成。

這批資料中，R128 的尺寸與形狀重拍波動最小，R129 次之。R61 的輪廓呈明顯圓角方形，平均直徑比原圖小約 109 nm；R128、R129 分別比原圖大約 28、35 nm。原圖不是實物真值，因此上述差距不能稱作尺寸誤差。更圓、更平滑也不能直接等於更正確。

'''+table+'''
尺寸與形狀重拍波動越小，代表同一批物體重拍後量到的結果越一致。R128 相較 R129，尺寸波動減少約 40%，形狀波動減少約 16%。配對重抽完整掃描所得差距範圍皆低於零；此證據限定這次拍攝、這九顆物體與目前讀取方法。

## 計算定義與範圍

- 四組使用完全相同的 30 次 ×31 位置 ×9 顆，共 33,480 個已保存邊界；每組 8,370 個。沒有挑掉不利樣本、重新訓練或改模型。
- 使用原論文 LSC 圓心、半徑與 64 個邊界點。直徑為兩倍 LSC 半徑。面積等效直徑、圓形程度、徑向起伏及二階／四階形狀分量保存在逐顆資料表，都是描述值，不是真值誤差。
- 尺度為相機像素 3.45 μm／20 倍，即名義 172.5 nm/px；尚未加入獨立倍率校正或 SEM 尺度不確定度。nm 數值會隨後續尺度校正同比改變。
- 每個相同位置序號、相同顆粒分別計算 30 次樣本變異數，再將 279 組變異數平均後開根號，得到表中尺寸重拍波動。這是每次測量的波動，不是 30 次平均值的不確定度，也不是完整總不確定度。
- 輪廓先以各自 LSC 圓心消除平移，不旋轉、不縮放；以固定影像角度插值為 720 方向。原始邊界仍只有 64 點，插值不增加實際解析度。先扣每條輪廓的平均半徑，再以相同方法計算角度與目標的平均重拍變異，得到形狀重拍波動。未扣平均半徑的完整輪廓波動另存 summary.csv。
- 最大尺寸偏離：每次直徑相對該位置、該顆粒 30 次平均的最大絕對差。不是對實物的最差誤差，也不是保證未來不會超過的界限。
- 另列每次掃描內 31 個位置的尺寸波動，分開呈現移動取樣造成的變化。位置序號對應同一移動程序；沒有強制 PI 實際位置完全相等。
- 範圍估計採 2,000 次完整掃描配對重抽，四組使用同一組抽樣次序，取百分位 95% 範圍；不把 8,370 顆次或 720 角度視為獨立樣本。未剔除時間漂移，結果包含本次工作階段的變動；不能外推不同樣品或不同日期。

## 已完成檢查

逐顆數量、位置與顆粒鍵無重複；理想圓、橢圓及平移不變性檢查通過；33,480 個徑向殘差結果與原有資料一致。另以分組資料表獨立重算尺寸波動、重新載入輪廓重算形狀波動，與摘要一致。三張圖已實際查看。原模型、原影像、先前位移成果與另一項訓練均未修改。

## 待同批參考到位後完成

確認九顆物體與參考一一對應，核對參考尺度及量測定義，再比較直徑差、逐方向輪廓差、局部最差差距及形狀差。形狀對齊只去除剛體位移／有根據的旋轉，不用自由縮放消去尺寸誤差。參考本身的尺度與邊界判讀誤差需獨立列入。既有另一批 SEM 成果不混入本表。

## 圖表與資料

![尺寸與形狀重拍比較](../results/shape_size/figures/repeatability.png)

![平均輪廓](../results/shape_size/figures/mean_contours.png)

![同一物體30次輪廓疊合](../results/shape_size/figures/thirty_repeat_contours.png)

資料位於 results/shape_size：summary.csv 總表、per_contour.csv 逐顆明細、per_scan.csv 每次掃描平均、matched_target_statistics.csv 各位置各顆统计、paired_scan_intervals.csv 配對差距範圍，以及四組徑向輪廓、來源雜湊與核對紀錄。scripts/shape_size_validation.py 可重算，scripts/publish_shape_size.py 核對並發布本成果。
'''
report=ROOT/'reports/R136_SHAPE_SIZE_RESULTS.md';report.write_text(text,encoding='utf-8')
body='<h1>輪廓、形狀與尺寸：30次重拍比較</h1><p>重拍比較完成；同批實物參考待提供，準確程度尚未判定。</p>'+s[['model','diameter_mean_nm','diameter_repeat_sd_nm','shape_repeat_sd_nm','diameter_repeat_absmax_nm']].round(3).to_html(index=False)
for p in sorted((OUT/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
body+='<h2>完整說明</h2><pre>'+html.escape(text.split('## 圖表與資料')[0])+'</pre>'
(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>R136 Shape and Size</title><style>body{max-width:1200px;margin:32px auto;font:17px/1.7 sans-serif;padding:0 20px}img{width:100%}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #bbb}pre{white-space:pre-wrap;font:inherit}</style>'+body,encoding='utf-8')
v=json.loads((OUT/'verification.json').read_text());v.update(independent_summary_recheck=True,figures_visually_reviewed=3)
(OUT/'verification.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
note='R136輪廓／形狀／尺寸重拍驗證：四組33480輪廓完成，R128尺寸／形狀波動13.558／13.560nm最小；實物準確度待使用者提供已確認存在的同批參考，不升級模型。'
link='[驗證報告](Experiments/R136_PIRepeatability/reports/R136_SHAPE_SIZE_RESULTS.md)'
p=REPO/'PROJECT_STATE.md'; t=p.read_text(encoding='utf-8-sig'); marker='<!-- R136_SHAPE_SIZE -->'
if marker not in t:
 t=t.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+marker+'\n'+note+' '+link+'\n',1)
 t=t.replace('### R136 R128追加完成','### R136 輪廓與尺寸重拍驗證\n\n'+note+' '+link+'\n\n### R136 R128追加完成',1);p.write_text(t,encoding='utf-8')
p=REPO/'Experiments/INDEX.md';t=p.read_text(encoding='utf-8-sig')
if marker not in t:p.write_text(t+'\n'+marker+'\n'+note+' [報告](R136_PIRepeatability/reports/R136_SHAPE_SIZE_RESULTS.md)\n',encoding='utf-8')
p=REPO/'ESTIMATOR_POLICY.json';data=json.loads(p.read_text(encoding='utf-8-sig'))
def update(x):
 if isinstance(x,dict):
  if x.get('round')=='R136' and x.get('experiment')=='Experiments/R136_PIRepeatability':
   x['shape_size_validation']={'status':'repeatability_complete_reference_pending','report':'Experiments/R136_PIRepeatability/reports/R136_SHAPE_SIZE_RESULTS.md','note':note,'formal_promotion':False}
  else:
   for y in x.values(): update(y)
 elif isinstance(x,list):
  for y in x:update(y)
update(data);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (ROOT/'HANDOFF.md').open('a',encoding='utf-8') as f:f.write('\n## Shape/size repeatability 2026-09-19\n'+note+' Same-sample truth path pending; do not replace with old R135 SEM. Results results/shape_size; report reports/R136_SHAPE_SIZE_RESULTS.md. No training touched.\n')
package=ROOT/'output/R136_Shape_Size_Repeatability.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
 for p in OUT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(OUT))
 z.write(report,'R136_SHAPE_SIZE_RESULTS.md')
 for name in ['shape_size_validation.py','publish_shape_size.py']:z.write(ROOT/'scripts'/name,'scripts/'+name)
with zipfile.ZipFile(package) as z:assert z.testzip() is None
print('Independent summary checks passed; 3 plots reviewed; ZIP CRC passed:',package)
