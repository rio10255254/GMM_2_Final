from pathlib import Path
import json,hashlib,shutil,ast,re,zipfile,datetime
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(r'D:\GMM_2_Final\Experiments\R130_Clean')
OLD=Path(r'D:\GMM_2_Final\Deliverables\R129_Corrected_Corner9_Thesis_Handoff_20260920')
P=Path(r'D:\GMM_2_Final\Deliverables\R130_Clean_Corrected_Corner9_Validation_Handoff_20260920')
assert not P.exists(), 'Never overwrite a previous handoff'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
locked=read(R/'config/source_lock.json');protected=read(R/'config/protected_sources.json')
for rel,h in locked.items():assert sha(R/rel)==h,rel
for x in protected:assert sha(Path(x['path']))==x['sha256'],x['path']
P.mkdir(parents=True)
sources=[]
def write(rel,s):
 p=P/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def js(rel,v):write(rel,json.dumps(v,ensure_ascii=False,indent=2))
def cp(src,rel):
 src=Path(src);dst=P/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 h=sha(src);assert sha(dst)==h
 sources.append(dict(path=str(dst.relative_to(P)).replace('\\','/'),source=str(src),sha256=h))
def tree(src,rel):
 for f in sorted(src.rglob('*')):
  if f.is_file() and '__pycache__' not in f.parts:cp(f,Path(rel)/f.relative_to(src))
a='01_Raw_R130_Comparison';b='02_R129_R130_Comparison_and_Runtime';c='03_Sampling_and_SEM';d='04_Training_and_Provenance';e='05_Verification_and_Sources';f='06_Script_Reference'
for x in [a,b,c,d,e,f]:(P/x).mkdir()
tree(R/'results/comparison',b+'/complete_three_method_tables')
tree(R/'results/independent_review',e+'/independent_review')
tree(OLD/'03_Sampling_and_SEM',c+'/inherited_sampling_reference')
for name in ['capture_plan.json','measurement_config.json','tracking.csv','calibration.json','sem_mapping_candidates.json','sem_points.npz','sem_scale.json']:
 cp(R/'evaluation'/name,c+'/'+name)
for model in ['Raw','R129','R130-Clean']:
 base=R/'results/centers' if model=='R130-Clean' else R/'evaluation/baseline_centers'/model
 tree(base,e+'/measured_centers/'+model)
for name in ['source_lock.json','protected_sources.json','evaluation_manifest.json','execution_context.json','USER_SPECIFICATION.md']:
 cp(R/'config'/name,d+'/original_config/'+name)
for name in ['config_r130_clean.yaml','DELIVERY_MANIFEST.json']:
 cp(R/name,d+'/'+name)
for name in ['run_config.json','training_complete.json','updates.jsonl','status.json','latest_checkpoint.json']:
 cp(R/'runs/formal_8192'/name,d+'/training/'+name)
tree(R/'runs/formal_8192/evaluations',d+'/training/evaluations')
cp(R/'runs/formal_8192/checkpoints/step08192.pth',d+'/final_model/step08192.pth')
cp(R/'reports/TRAINING_PROVENANCE.md',d+'/TRAINING_PROVENANCE.md')
cp(R/'reports/R130_CLEAN_RESULTS.md','07_Original_Report/R130_CLEAN_RESULTS.md')
tree(R/'reports/figures','07_Original_Report/figures')
cp(R/'reports/figures/training_curves.png',d+'/training_curves.png')
for q in R.glob('*.py'):cp(q,f+'/execution_source/'+q.name)
for folder in ['optical','evaluation']:
 for q in (R/folder).glob('*.py'):cp(q,f+'/execution_source/'+folder+'/'+q.name)
cp(R/'results/independent_result_review.py',f+'/independent_result_review.py')
cp(Path(__file__),f+'/build_validation_handoff.py')
for q in (R/'results').glob('*.json'):cp(q,e+'/execution_audits/'+q.name)
cp(R/'results/reconstruction_runtime.csv',b+'/reconstruction_runtime.csv')
cp(R/'results/first_frame_visual_check.png',a+'/figures/first_frame_visual_check.png')
for name in ['native_nine_example.png','worst_adjacent_observation.png','independent_mean_shapes.png']:
 cp(R/'reports/figures'/name,b+'/figures/'+name)
C=pd.read_csv(R/'results/comparison/all_circles.csv');D=pd.read_csv(R/'results/comparison/all_displacements.csv')
assert len(C)==25110 and len(D)==5400
assert C.groupby('model').size().eq(8370).all()
assert not C.duplicated(['model','run','index','pillar_id']).any()
assert not D.duplicated(['model','run','kind','j']).any()
models=['Raw','R129','R130-Clean'];cols={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722'}
for name in ['all_circles','all_displacements','displacement_summary','position_statistics','scan_statistics','shape_size_summary','SEM_comparison','endpoint_30um']:
 df=pd.read_csv(R/'results/comparison'/f'{name}.csv');df[df.model.isin(['Raw','R130-Clean'])].to_csv(P/a/f'{name}.csv',index=False)
ci=pd.read_csv(R/'results/comparison/paired_scan_intervals.csv');ci[ci.reference=='Raw'].to_csv(P/a/'paired_scan_intervals.csv',index=False)
plan=read(R/'evaluation/capture_plan.json');u=np.array(read(R/'evaluation/calibration.json')['axis_unit_vector']);runs=[r['run'] for r in plan['runs']]
ind=[];pillars=[];positions=[];angular=[];check=[]
geom=pd.read_csv(R/'results/comparison/shape_size_summary.csv')
for m in models:
 df=C[C.model==m].copy();df['run_order']=df.run.map({v:i for i,v in enumerate(runs)});df=df.sort_values(['run_order','index','pillar_id'])
 xy=df[['center_x_px','center_y_px']].to_numpy().reshape(30,31,9,2);di=df.diameter_nm.to_numpy().reshape(30,31,9)
 with np.load(R/'results/comparison'/f'{m}_radial_profiles.npz') as z:rad=z['radius_nm'].astype('float64');angle=z['angle_rad']
 sh=rad-rad.mean(-1,keepdims=True)
 for metric,val in [('diameter_mean_nm',di.mean()),('diameter_repeat_sd_nm',np.sqrt(di.var(0,ddof=1).mean())),('contour_repeat_sd_nm',np.sqrt(rad.var(0,ddof=1).mean())),('shape_repeat_sd_nm',np.sqrt(sh.var(0,ddof=1).mean()))]:
  err=abs(val-float(geom[geom.model==m].iloc[0][metric]));assert err<1e-4,(m,metric,err);check.append(err)
 for k in range(9):pillars.append(dict(model=m,pillar_id=k+1,diameter_mean_nm=di[:,:,k].mean(),diameter_repeat_sd_nm=np.sqrt(di[:,:,k].var(0,ddof=1).mean()),contour_repeat_sd_nm=np.sqrt(rad[:,:,k].var(0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(sh[:,:,k].var(0,ddof=1).mean())))
 for j in range(31):positions.append(dict(model=m,index=j,diameter_mean_nm=di[:,j].mean(),diameter_repeat_sd_nm=np.sqrt(di[:,j].var(0,ddof=1).mean()),contour_repeat_sd_nm=np.sqrt(rad[:,j].var(0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(sh[:,j].var(0,ddof=1).mean())))
 for k in range(720):angular.append(dict(model=m,angle_deg=float(np.degrees(angle[k])),contour_repeat_sd_nm=np.sqrt(rad[:,:,:,k].var(0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(sh[:,:,:,k].var(0,ddof=1).mean())))
 for ri,run in enumerate(runs):
  for kind in ['adjacent','start']:
   for j in range(1,31):
    i=j-1 if kind=='adjacent' else 0;delta=xy[ri,j]-xy[ri,i];row=D[(D.model==m)&(D.run==run)&(D.kind==kind)&(D.j==j)].iloc[0]
    assert abs((np.median(delta,axis=0)@u*.1725-row.pi_displacement_um)*1000-row.error_nm)<1e-8
    for k in range(9):ind.append(dict(model=m,run=run,run_index=ri+1,kind=kind,i=i,j=j,pillar_id=k+1,pi_displacement_um=row.pi_displacement_um,image_displacement_um=delta[k]@u*.1725,error_nm=(delta[k]@u*.1725-row.pi_displacement_um)*1000))
for name,rows in [('individual_circle_displacements',ind),('nine_pillar_size_shape',pillars),('geometry_by_position',positions),('angular_repeatability',angular)]:
 df=pd.DataFrame(rows);df.to_csv(P/b/(name+'.csv'),index=False);df[df.model.isin(['Raw','R130-Clean'])].to_csv(P/a/(name+'.csv'),index=False)
assert len(ind)==48600
# Source index includes every reconstructed image; images remain at their original location.
runtime=pd.read_csv(R/'results/reconstruction_runtime.csv');assert len(runtime)==930
ix=[]
for row in runtime.itertuples():
 src=ast.literal_eval(row.source);ix.append(dict(run=row.run,index=row.index,raw_path=src['path'],raw_sha256=src['sha256'],reconstruction_path=row.output_path,reconstruction_sha256=row.output_sha256,checkpoint_sha256=row.checkpoint_sha256))
pd.DataFrame(ix).to_csv(P/e/'all_930_image_sources.csv',index=False)
# A complete real example is bundled for viewing and remeasurement, with unchanged numerical output.
cp(Path(ix[0]['raw_path']),a+'/real_example/Raw.bmp');cp(Path(ix[0]['reconstruction_path']),a+'/real_example/R130-Clean.npz')
write(a+'/real_example/README.md','第一趟第零位置的原始完整影像與 R130 重建數值。NPZ 的 output 為 0–1 灰階；量測使用此數值，不使用展示圖。其餘 929 張的來源與雜湊見 05_Verification_and_Sources/all_930_image_sources.csv。\n')
def savefig(fig,name,folder=a):
 dest=P/folder/'figures';dest.mkdir(exist_ok=True);fig.savefig(dest/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(dest/(name+'.svg'),bbox_inches='tight');plt.close(fig)
for group,folder in [(['Raw','R130-Clean'],a),(models,b)]:
 fig,axes=plt.subplots(1,2,figsize=(12,4.3))
 for ax,kind in zip(axes,['adjacent','start']):
  for m in group:
   v=D[(D.model==m)&(D.kind==kind)].groupby('j').error_nm.agg(['mean','std']);ax.plot(v.index,v['mean'],label=m,color=cols[m]);ax.fill_between(v.index,v['mean']-v['std'],v['mean']+v['std'],alpha=.13,color=cols[m])
  ax.axhline(0,color='black',lw=.6);ax.set(xlabel='Position index',ylabel='PI-relative error (nm)',title=kind+' | mean +/- 1 SD, 30 scans');ax.legend();ax.grid(alpha=.2)
 savefig(fig,'displacement_mean_sd',folder)
 fig,axes=plt.subplots(1,3,figsize=(12,4))
 for ax,metric,title in zip(axes,['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'],['Diameter repeatability','Contour repeatability','Size-removed shape repeatability']):
  vals=[float(geom[geom.model==m].iloc[0][metric]) for m in group];bars=ax.bar(group,vals,color=[cols[m] for m in group]);ax.bar_label(bars,fmt='%.2f');ax.set(title=title,ylabel='SD (nm)',ylim=(0,max(vals)*1.22));ax.tick_params(axis='x',rotation=15)
 savefig(fig,'geometry_repeatability',folder)
fig,axes=plt.subplots(1,2,figsize=(12,4))
pp=pd.DataFrame(pillars)
for ax,key,title in zip(axes,['diameter_repeat_sd_nm','contour_repeat_sd_nm'],['Diameter','Contour']):
 for m in models:
  v=pp[pp.model==m];ax.plot(v.pillar_id,v[key],marker='o',label=m,color=cols[m])
 ax.set(xlabel='Pillar ID',ylabel='Repeatability SD (nm)',title=title);ax.legend();ax.grid(alpha=.2)
savefig(fig,'per_pillar_repeatability',b)
# Standalone narrative: enough context for a reader without folder access to originals.
write('START_HERE.md','''# R130-Clean 完整驗證結果包

先讀 [完整說明與論文使用建議](HANDOFF_FOR_THESIS.md)，再看 [原圖與重建比較](01_Raw_R130_Comparison/README.md)。

- **01**：原圖與 R130 的位移、尺寸、輪廓結果；全部逐筆數據、圖表及一組完整真實影像。
- **02**：與 R129 的比較、執行時間、三方法完整資料。
- **03**：選取哪九顆、拍攝資料、量測設定、SEM 的兩種方向對應。
- **04**：從零訓練的來源說明、完整訓練紀錄、設定、最終模型。
- **05**：三方法全部量測輪廓與圓心、獨立核對、930 張原圖及重建來源索引。
- **06**：原始分析程式與本包整理程式，供追溯；不是一鍵重新訓練環境。
- **07**：[原始完整結果報告](07_Original_Report/R130_CLEAN_RESULTS.md)，連同其原有圖表保留。

本包可獨立閱讀，不必連回原資料夾才能理解結果。完整 930 張重建大檔仍在原位置，未重複搬入；包內附完整索引與一組原尺寸範例。所有量測數值與輪廓點均已帶入。

核對方法：在本資料夾執行 `python verify_package.py`。它只讀取並比對，不更改檔案或核對基準。MANIFEST.json 是本次封裝內容清單，不取代原實驗的獨立查核。
''')
sumtab=pd.read_csv(R/'results/comparison/displacement_summary.csv').round(4).to_markdown(index=False)
gtab=geom.round(4).to_markdown(index=False)
stab=pd.read_csv(R/'results/comparison/SEM_comparison.csv').round(4).to_markdown(index=False)
write('HANDOFF_FOR_THESIS.md',f'''# R130-Clean 驗證全貌與論文使用建議

## 結論
R130 保留了 R129 的主要位移穩定性，尺寸重拍更穩定，處理速度較快。它沒有解決尺寸偏大的問題，也不是每一項形狀結果都較好。本包沒有宣布更換論文模型或正式基準。

## 做了什麼
從零訓練 8192 次、16 個循環；512 個合成訓練來源、128 個開發來源、128 個既有生成測試來源。沒有載入舊模型權重；實測 PSF 全程關閉，SEM、PI 和真實拍攝沒有進入訓練。這不代表實測 PSF 融合的舊論文特色仍存在：R130 是純神經、原尺寸、四次共享修正的版本，不能直接沿用 R129／V42 的光學融合創新敘述。

固定使用最後一次訓練模型，並非按真實結果挑最好的一次。最終模型識別：559afeff214ff15e92ce910d7df7ead12994074b6173dabe9a7f21a8b40372cc。

## 真實驗證如何做
同一批樣本、同一拍攝工作階段，30 趟重拍，每趟 31 個位置，共 930 張，每張同一組角落九顆，共每方法 8370 次圓量測。影像 1544×2064、20×、正常曝光 3000 μs，固定尺度 172.5 nm/px。三方法皆用同一取樣、追蹤、ACM、最大梯度邊界及最小平方圓擬合。重建數值以完整浮點影像量測。

每兩位置先逐顆求圓心差，對九顆的 x、y 分量各取中位數，再投影至固定移動軸；與 PI 回授的差以 nm 表示。相鄰位移為 j 減 j−1；相對起點為 j 減 0，沒有再扣一次位移，也不是逐段中位数相加。

這是已使用過的評估資料，並非未見過的保留資料。九顆不等於九個獨立樣本，720 個插值方向也不等於 720 個實際新量測點；每圈實際取 64 點。

## 位移數據
{sumtab}

短步與 R129 的平均差只有 −0.0039 nm，整趟配對的差值範圍跨過零，不能說有確定勝負。原圖到 R130 的短步平均差由 8.167 降至 4.121 nm。各位置重拍標準差先各自計算，再取算術平均作為位移重複性。

## 尺寸與輪廓
{gtab}

尺寸／輪廓重複性：固定位置與固定顆粒先在 30 趟間算樣本變異數，再平均變異數並開根號。輪廓以各自圓心為基準，去尺寸形狀另外扣掉每圈平均半徑。它們回答的是重拍有多一致，不能直接說尺寸更準。逐顆、逐位置與逐角度資料均附於 01／02。

## SEM 對照
{stab}

完整徑向差包含尺寸差，去尺寸形狀差另列。SEM 方向仍有兩個既有候選，兩者都保留，不能挑有利者當作唯一已證實方向。R130 平均直徑較 SEM 大約 219.41 nm；R129 約 224.47 nm。此處沿用既有尺度與 SEM 參考，不等於完整校準的不確定度或絕對精度證明。

## 範圍與不確定性
已附 30 趟整趟配對的 95% 區間；另外有時間區塊敏感度，早 6 趟和晚 24 趟分開取連續 3 趟區塊，沒有跨越拍攝間隔。這些是本次差值與重拍變動的估計，未把 PI、尺度、SEM 與其他系統誤差合成完整總不確定度。沒有複用 R129 舊的不確定度數字冒充 R130。

## 速度
本輪 930 張純重建中位數 1.384 秒／張，含讀取與寫出 1.867 秒／張。R129 歷史含讀寫中位數 11.182 秒／張；約六倍僅為既有整體時間描述，本輪沒有重新做 R129 同條件速度測試。完整影像與分塊輸出最大差 1.49×10⁻⁷，通過事先設定的容許差，但不是逐位元相同。

## 論文怎麼使用
若之後決定採用 R130，正文可只放原圖與 R130，R129 比較留作選型依據。建議依序呈現：模型與資料來源、實際九顆位置與量測步驟、位移平均差與重拍範圍、尺寸／輪廓重複性、SEM 尺寸與形狀的分開對照。消融實驗仍未在這包新增，不應假裝做過。來源可追溯和修正步驟可檢查，不等於已證明完整可解釋性。

## 本次核對
封裝前核對原執行程式與受保護歷史資料未變動；重新由三方法全部圓心計算 5400 筆整體位移，再核對尺寸、輪廓彙總。既有独立審查曾核對 930 張重建雜湊與 8370 次新模型圓擬合。新增加的逐顆表是同一批已量測資料的整理，不是額外獨立實驗。

包內提供全部量測點與資料，原本大型影像保留原處；相對連結可在解壓後使用。執行來源程式保留原始路徑語意，讀者不能假設它們已改造成可攜式一鍵重跑環境。
''')
write(a+'/README.md','''# 原圖與 R130：主要驗證結果

完整數據與定義見 [交接說明](../HANDOFF_FOR_THESIS.md)。本區只放原圖與 R130，便於後續以單一模型撰寫。

- all_circles.csv：16740 次圓心、直徑與量測資訊。
- all_displacements.csv：3600 筆九顆合成的位移。
- individual_circle_displacements.csv：32400 筆逐顆位移；不代表獨立樣本數。
- position_statistics.csv：120 組固定位置統計；scan_statistics.csv：120 組整趟統計。
- nine_pillar_size_shape.csv、geometry_by_position.csv、angular_repeatability.csv：逐顆、逐位置、逐方向重拍穩定性。
- SEM_comparison.csv：兩種方向候選的尺寸和形狀差。
- paired_scan_intervals.csv：以完整重拍趟次計算的配對差值範圍。

![位移平均與重拍範圍](figures/displacement_mean_sd.png)
![尺寸與輪廓重拍](figures/geometry_repeatability.png)
![完整視野與局部重建](figures/first_frame_visual_check.png)

數字圖另附 SVG 可縮放版本。真實影像範例見 real_example，完整三方法影像展示見 02。
''')
write(b+'/README.md','''# R129 對照與速度

完整三方法原始分析表在 complete_three_method_tables，未改寫數據。原圖、R129、R130 分別以灰、藍、橘表示。

![位移比較](figures/displacement_mean_sd.png)
![重拍比較](figures/geometry_repeatability.png)
![逐顆比較](figures/per_pillar_repeatability.png)
![同一真實影像](figures/native_nine_example.png)
![去尺寸形狀與 SEM](figures/independent_mean_shapes.png)
![最大相鄰差值個案](figures/worst_adjacent_observation.png)

SEM 圖只示意候選方向一，兩種方向的全部數字在 SEM_comparison.csv；不能只採有利方向。影像示例不是全部影像細節保真的證明。

reconstruction_runtime.csv 是本輪 930 張時間與來源。完整及分塊速度／記憶體在 05/execution_audits 的 profile.json、profile_tiled_fresh.json。R129 是歷史整體時間，不是本輪重新測速。
''')
write(c+'/README.md','''# 取樣、量測與 SEM

![實際九顆](inherited_sampling_reference/selected_nine.png)

這次直接沿用 R129 更正後的同一組角落九顆。capture_plan.json 列出 30 趟、930 張與 PI；tracking.csv 是固定追蹤種子；measurement_config.json 是三方法共同量測設定；calibration.json 是固定軸和尺度。主分析使用 nominal_um_per_px=0.1725，未改用估算尺度。

SEM 保留兩個方向候選、原始參考點與尺度。inherited_sampling_reference 完整保留前一包的取樣與方向證據，屬於沿用來源，沒有宣稱本次重新確定方向。歷史對照圖片與 R129 處理邊界說明不等於 R130 的處理設計；R130 使用完整影像重建。
''')
write(d+'/README.md','''# 訓練與模型來源

[訓練來源說明](TRAINING_PROVENANCE.md) 保留原始報告。training 提供全部 8192 次更新紀錄與 17 次開發檢查；final_model 是本次實際使用的最後模型。original_config 包含執行前鎖定的規格與來源紀錄，沒有重新接受不同的雜湊。

![訓練曲線](training_curves.png)

R130 沒有使用實測 PSF 融合；不是保留全部 R129 光學特色的改名版本。訓練只用既有合成配對、從零開始。完整訓練資料仍在原實驗根目錄；此包是結果交接，不是一鍵完整重新訓練包。
''')
write(e+'/README.md','''# 核對與來源

measured_centers 含 Raw、R129、R130 全部 90 組逐趟圓心及輪廓點。每個 NPZ 的 points 是 31×9×64×2 個座標。三方法半徑方向資料在 02/complete_three_method_tables。

all_930_image_sources.csv 列出每張原圖、重建、最終模型的識別與原路徑；完整重建實體仍在 H:\\GMM_2_Final_Archive\\active_runs\\R130_Clean_20260920\\reconstruction。

execution_audits 與 independent_review 是原執行時核對紀錄的原樣副本。當中的時間、絕對路徑屬於當時環境；本次包的核對在 packaging_validation.json。包的完整性比對只證明內容沒有變動，不會自動把研究结论升級成獨立準確度證明。
''')
write(f+'/README.md','''# 程式參考

execution_source 保存原執行程式，不重新訓練、不改模型、不更改量測。independent_result_review.py 是執行後另行查核；build_validation_handoff.py 是這次封裝及補齊逐顆數據的程式。

這些程式保留實際工作環境的路徑與相依套件，供讀者檢查公式與來源；不是解壓後可直接執行全部訓練的一鍵環境。verify_package.py 則可獨立核對本包內容。
''')
js(e+'/packaging_validation.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),locked_execution_files_verified=len(locked),protected_originals_verified=len(protected),all_circles=25110,aggregate_displacements_recomputed=5400,individual_displacements=48600,raw_r130_circles=16740,raw_r130_displacements=3600,raw_r130_individual_displacements=32400,geometry_recompute_max_difference_nm=max(check),all_930_images_indexed=True,source_artifacts_modified=False,full_image_collection_duplicated=False))
js('SOURCE_COPIES.json',sources)
write('verify_package.py', '''from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
items=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for item in items:
 p=(root/item['path']).resolve()
 if not p.is_relative_to(root) or not p.is_file():errors.append(item['path']);continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8388608),b''):h.update(chunk)
 if h.hexdigest()!=item['sha256']:errors.append(item['path'])
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST.json'}
expected={x['path'] for x in items}
errors.extend(sorted(actual^expected))
if errors:print('FAIL:',errors);sys.exit(1)
print('PASS:',len(items),'payload files verified; no files modified')
''')
# Validate every Markdown local link before sealing this newly created copy.
for p in P.rglob('*.md'):
 if p.parent.name=='execution_source':continue
 if p.name in ['TRAINING_PROVENANCE.md','USER_SPECIFICATION.md']:continue
 for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if '://' in target or re.match(r'^[A-Za-z]:',target):continue
  assert (p.parent/target.split('#')[0]).exists(),(p,target)
items=[dict(path=p.relative_to(P).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.rglob('*')) if p.is_file()]
js('MANIFEST.json',items)
for x in protected:assert sha(Path(x['path']))==x['sha256']
for rel,h in locked.items():assert sha(R/rel)==h
print(json.dumps(dict(folder=str(P),files=len(items),size_MB=sum(x['bytes'] for x in items)/1024**2,source_copies=len(sources),geometry_max_error_nm=max(check)),ensure_ascii=False))
