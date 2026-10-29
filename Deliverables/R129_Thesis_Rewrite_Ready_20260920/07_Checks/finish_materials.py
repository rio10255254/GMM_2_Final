from pathlib import Path
import json,hashlib,shutil,re,sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[3]

sys.stdout.reconfigure(encoding='utf-8')
R=Path(str(PROJECT_ROOT));E=R/'Experiments/R129_OpticalPriorHybrid'
O=R/'Deliverables/R129_Thesis_Rewrite_Ready_20260920';H=O/'04_Results/R129_Handoff'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(rel,t):
 p=O/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(rel,o):write(rel,json.dumps(o,ensure_ascii=False,indent=2))
copies=load(O/'07_Checks/source_copies.json')
def cp(src,rel):
 dst=O/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 h=sha(src);assert sha(dst)==h;copies.append(dict(source=str(src),destination=rel,sha256=h))

cp(E/'reports/R129_THESIS_FINAL_REWRITE_PLAN_20260920.md','00_Plan/COMPLETE_REWRITE_PLAN.md')

# Redraw saved contour data for page-ready margins and a single paper method name.
# The untouched original figures remain in 04_Results/R129_Handoff.
centers={m:pd.read_csv(H/'01_Raw_R129_Comparison/all_contours_16740.csv').query('model == @m') for m in ['Raw','R129']}
arrays={}
for m in ['Raw','R129']:
 a=[]
 for run,g in centers[m].groupby('run_index',sort=True):
  name=g.run.iloc[0]
  with np.load(H/f'04_Verification_and_Sources/centers/{m}/{name}.npz') as z:p=z['points']
  c=g.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].values.reshape(31,9,2)
  a.append((p-c[:,:,None,:])*172.5)
 arrays[m]=np.stack(a)
for pos,name in [(0,'F07_contours_start'),(30,'F08_contours_end')]:
 fig,axs=plt.subplots(3,3,figsize=(10,10),layout='constrained')
 for j,ax in enumerate(axs.flat):
  for m,color in [('Raw','#92979c'),('R129','#1486a8')]:
   for k in range(30):
    p=arrays[m][k,pos,j];p=np.vstack([p,p[0]])
    ax.plot(p[:,0],p[:,1],color=color,alpha=.16,lw=.8)
  ax.set(xlim=(-1800,1800),ylim=(-1800,1800),title=f'Pillar {j+1}',xlabel='x (nm)',ylabel='y (nm)');ax.set_aspect('equal');ax.tick_params(labelsize=8)
 from matplotlib.lines import Line2D
 fig.legend([Line2D([],[],color='#92979c'),Line2D([],[],color='#1486a8')],['Raw','MOSR'],loc='lower center',bbox_to_anchor=(.5,1.01),ncol=2)
 fig.suptitle(f'Position {pos}: 30 repeats, centers aligned; no size normalization',fontsize=12)
 for ext in ['png','svg']:fig.savefig(O/f'05_Paper_Figures/{name}.{ext}',dpi=180,bbox_inches='tight')
 plt.close(fig)
# These two curated copies have intentionally become derived figures; provenance
# keeps the source originals in the full handoff and records the transform.
copies=[c for c in copies if c['destination'].replace('\\','/') not in ['05_Paper_Figures/F07_contours_start.png','05_Paper_Figures/F08_contours_end.png']]

# Paper selection illustration shows only the current nine, not old internal ROIs.
import cv2
raw=cv2.imread(str(O/'05_Paper_Figures/example_source/first_raw.bmp'),0)
xy=np.asarray(load(H/'04_Verification_and_Sources/config/sem_corner9_lsc_plan.json')['base_centers'])
fig,axs=plt.subplots(1,2,figsize=(12,6),width_ratios=[2.2,1],layout='constrained')
axs[0].imshow(raw,cmap='gray',vmin=0,vmax=255);axs[0].scatter(xy[:,0],xy[:,1],facecolors='none',edgecolors='#00b5d9',s=35,lw=1.2)
axs[0].set(title='Measured field: fixed nine pillars',xlabel='Image x (pixels)',ylabel='Image y (pixels)')
axs[1].imshow(raw,cmap='gray',vmin=0,vmax=255);axs[1].scatter(xy[:,0],xy[:,1],facecolors='none',edgecolors='#00b5d9',s=200,lw=1.2)
for i,(x,y) in enumerate(xy,1):axs[1].text(x+7,y-7,str(i),color='#e35a00',fontsize=11)
axs[1].set(xlim=(1560,1682),ylim=(817,694),title='Fixed target identities',xlabel='Image x (pixels)',ylabel='Image y (pixels)')
for ext in ['png','svg']:fig.savefig(O/f'05_Paper_Figures/F05_selected_nine.{ext}',dpi=180,bbox_inches='tight')
plt.close(fig)
copies=[c for c in copies if c['destination'].replace('\\','/')!='05_Paper_Figures/F05_selected_nine.png']

figs=[
('F01','4.4','F01_model_and_measurement.png','MOSR重建與共同量測流程','單張觀測影像先經實測光學處理，再由共享參數的程序修正四次，最後將受限細節加入原圖。原圖及重建影像以相同ACM與取邊流程量測。SEM與平台讀值屬外部參照。','package-local hybrid.py, optics.py, reconstruction.py, output_policy.py','方法示意，不是模組消融或精度證明'),
('F02','4.5／5.4','F02_training_examples.png','合成訓練資料範例','每列為一種資料類別，依序為觀測影像A、乾淨目標A及已知平移的觀測影像B。顯示中央128×128區域；輸入依第一循環雜訊設定重建，與當時實際訓練紀錄一致。各類別選編號最小的訓練母場景。','03_Dataset/example_sources.json','這些是生成的訓練資料，不是真實SEM答案；B圖不是A圖的重建結果'),
('F03','5.4／6.2.1','F03_training_and_development.png','接續訓練與開發資料的變化','左圖為每128次更新的訓練目標平均，右圖為固定128個開發母場景的平均目標。橫軸從本次接續訓練開始計算，不包含先前初始化訓練。','02_Method_and_Training/training_curve_all_steps.csv; development_curve.csv','生成資料的目標下降不能直接稱真實量測改善；兩圖群體不同'),
('F04','4.7／6.2.3','F04_ACM_and_final_boundary.png','ACM粗輪廓與最後量測邊界','同一首掃描、首張、第一顆物件，兩欄分別為原圖與MOSR重建。黃虛線為保存的ACM粗輪廓，藍線為沿法線尋找最大灰階梯度後的量測點連線。兩欄使用相同灰階範圍與像素位置。','05_Paper_Figures/example_source/provenance.json','示意取邊步驟，不是SEM真值或30次統計；未重新平滑邊界'),
('F05','5.2／6.2.2','F05_selected_nine.png','修正後九顆取樣位置','選取十字交界附近固定3×3九顆，追蹤由原始影像決定；新九顆與舊中央九顆分開。','04_Results/R129_Handoff/03_Sampling_and_SEM/selected_nine.png','位置修正不是按模型成績挑選物件'),
('F06','6.2.5','F06_displacement_mean_sd.png','位移平均差距與重拍波動','曲線為30次掃描在固定位置的平均影像位移減PI回授值，陰影為±1樣本標準差。左圖為相鄰約1μm短步，右圖為距起點約1–30μm。主讀值由九顆圓心差分量中位數得到。','04_Results/R129_Handoff/01_Raw_R129_Comparison/overlay_mean_sd_plot_data.csv','陰影不是95%總不確定度；九顆合併成績不能稱每顆的絕對定位精度'),
('F07','6.2.4','F07_contours_start.png','起始位置30次輪廓疊合','九顆在位置0的30次輪廓；各次只扣除自己的圓心，保持相同尺度，不縮放或旋轉。原圖灰色，MOSR藍色。使用原始64個取邊點。','04_Results/R129_Handoff/04_Verification_and_Sources/centers','輪廓集中表示讀取重複性，不等於已知真邊界'),
('F08','6.2.4','F08_contours_end.png','末端位置30次輪廓疊合','與起點圖使用相同物件、尺度與畫法，展示位置30的30次重拍輪廓。','04_Results/R129_Handoff/04_Verification_and_Sources/centers','起點與終點是固定展示位置，不按結果選最好案例'),
('F09','6.2.4','F09_diameter_and_SEM.png','尺寸平均值與重拍波動','左圖為九顆平均直徑及SEM集合參照，右圖為各位置的尺寸重拍波動。穩定性與SEM平均差距分別呈現。','04_Results/R129_Handoff/01_Raw_R129_Comparison/diameter_by_position_62.csv','平均尺寸差不是逐顆平均絕對誤差；參照尺度等不確定度未完全納入'),
('F10','6.2.4','F10_SEM_contours_inferred.png','SEM與光學輪廓對照','黑線為既有SEM，灰線為原圖、藍線為MOSR。逐顆對應採目前左右鏡像工作推定，另一方向的比較數值另表保留。','04_Results/R129_Handoff/01_Raw_R129_Comparison/SEM_direction_sensitivity.csv','方向不是唯一確認；去平均半徑的形狀結果不可改稱完整輪廓準確度')]
pd.DataFrame(figs,columns=['id','chapter','file','title','caption','source','qualification']).to_csv(O/'00_Plan/figure_caption_register.csv',index=False,encoding='utf-8-sig')
lines=['# 圖表與圖說準備','', '正式Word編號依排版更新；F01–F10為備稿識別。四張新方法／訓練圖已備PNG與SVG，輪廓起末圖亦備向量版。','']
for fid,ch,name,title,cap,source,q in figs:
 lines += [f'## {fid} {title}',f'建議位置：{ch}。 [圖檔](../05_Paper_Figures/{name})','',cap,'',f'判讀範圍：{q}',f'來源：`{source}`','']
write('00_Plan/FIGURES_AND_CAPTIONS.md','\n'.join(lines))

rows=pd.read_csv(H/'01_Raw_R129_Comparison/main_comparison.csv')
labels={'mae_nm':'平均絕對PI差距','repeatability_nm':'固定位置重拍標準差平均','maximum_error_nm':'本次最大絕對PI差距','diameter_repeat_sd_nm':'直徑重拍波動','contour_repeat_sd_nm':'輪廓重拍波動（保留尺寸）','shape_repeat_sd_nm':'形狀重拍波動（去平均半徑）','diameter_repeat_absmax_nm':'相對同位置平均的最大直徑偏離'}
rows['指標']=rows.metric.map(labels);rows.to_csv(O/'04_Results/T01_main_results.csv',index=False,encoding='utf-8-sig')
cp(H/'01_Raw_R129_Comparison/endpoint_30um.csv','04_Results/T02_endpoint.csv')
cp(H/'01_Raw_R129_Comparison/SEM_group_mean_size.csv','04_Results/T03_SEM_size.csv')
cp(H/'01_Raw_R129_Comparison/SEM_direction_sensitivity.csv','04_Results/T04_SEM_shape_directions.csv')
cp(O/'03_Dataset/category_counts.csv','04_Results/T05_training_composition.csv')
config=load(O/'02_Method_and_Training/training.json')
settings=[('訓練母場景',512),('開發母場景',128),('既有生成測試母場景',128),('接續訓練循環',16),('接續更新次數',8192),('共享更新次數',4),('影像目標權重',1),('梯度目標權重',.2),('配對殘差權重',.2),('最高學習率',.0001),('最低學習率',.00001),('暖身更新次數',128),('權重衰減',.00001),('梯度上限',5)]
pd.DataFrame(settings,columns=['item','value']).to_csv(O/'04_Results/T06_training_settings.csv',index=False,encoding='utf-8-sig')
write('04_Results/TABLE_GUIDE.md','''# 正文表格來源

T01：主要位移、尺寸及輪廓重拍結果，原圖與MOSR，單位nm。T02：30μm終點，與全路徑分開。T03：九顆集合平均SEM尺寸差。T04：兩種SEM方向的形狀與完整輪廓差。T05：实际訓練分類數量。T06：接續訓練設定。

CSV欄位保留R129以維持資料身分；Word中顯示本文方法名稱MOSR。小數保留來源精度，排版再四捨五入。不得合併不相同群體、改用舊中央九顆數字或將形狀波動改稱尺寸準確度。

完整逐顆、逐位置、兩種SEM方向和不確定度分量仍在R129_Handoff內。正文無需全部展開，但相關限制與數據不得改寫。
''')

write('00_Plan/WRITING_PASSAGES.md','''# 可供改稿的核心段落

以下是依現有證據整理的段落材料，尚未合入Word，不代表整篇論文已改完。文獻引用沿原稿核對後保留。

## 方法主旨

本研究以正常拍攝條件下的顯微影像量測為目的，提出結合實測光學資訊的MOSR重建流程。方法在影像輸入端融入固定光學先驗，再由共享參數的重建程序進行四次修正，並以原始影像為參照限制最後加入的細節。重建輸出維持原始影像尺寸，後續使用一致的輪廓與圓心量測方式，評估影像重建對實際量測結果的影響。

## 訓練資料與策略

訓練資料由程序生成，涵蓋不規則曲線、線條與交會、密集結構及紋理邊界，並包含清楚影像、雜訊與平坦區域控制。512個母場景用於訓練，另有128個開發母場景及128個既有生成測試母場景。母場景先分組，再建立觀測影像、目標影像及已知平移配對，避免同一幾何來源跨組。每次循環重新加入雜訊，新增的雜訊實現不另計為獨立幾何樣本。

模型由已完成前期訓練的初始化接續學習，進行16個資料循環、8192次更新。此階段使用影像差異、邊緣差異及已知平移下的配對殘差三項要求；完整初始化來源另於實作記錄說明。生成訓練目標與實拍／SEM評估資料分開，固定光學資料的校正來源亦獨立交代。

## ACM與最後量測輪廓

為維持重建前後比較的一致性，原始影像與MOSR影像採用相同量測程序。首先以ACM求得粗輪廓，再沿粗輪廓法線搜尋最大灰階梯度位置，形成最後的邊界取樣點。由這些點求得圓心與半徑，並計算位移、尺寸與輪廓特性。ACM粗輪廓、最終邊界點與擬合圓具有不同用途，在方法示意中分別標示。

## 位移結果

在同片樣品、同一拍攝工作階段的30次掃描中，修正後九顆物件每次均有31張影像。相鄰短步的九顆合併讀值相對PI回授之平均絕對差距，由原圖8.167nm降至MOSR的4.125nm，固定步位置的平均重拍標準差由9.725nm降至4.251nm；30次掃描的平均短步差距均降低。此結果支持已測條件下的短步量測改善，九顆合併讀值不等同單顆絕對定位精度。

## 輪廓結果

在同一位置、同一物件的30次比較中，保留尺寸變化的輪廓重拍波動由63.758nm降至18.437nm，降低約71.1%；扣除每條輪廓平均半徑後的形狀波動由61.667nm降至15.789nm，降低約74.4%。九顆的輪廓重拍波動皆降低，起始及末端位置疊圖顯示重建後取邊結果較為集中。這些結果反映輪廓讀取穩定性，不直接表示所有邊界都更接近實物。

## SEM與簡短限制

依目前推定的SEM對應方向，扣除平均半徑後的形狀差距由56.348nm降至32.636nm；另一候選方向下亦有改善。方向尚未唯一確認，圖說保留其判讀範圍。集合平均尺寸偏大及長距離終點偏差仍存在，因此本文將重拍穩定性與完整尺寸準確度分開討論，不以任一單一指標概括全部量測能力。

## 結論主句

本研究所提出的MOSR流程，在已測的正常實拍條件下改善短步位移及輪廓讀取的重拍穩定性，並以一致的ACM取邊程序、平台回授與SEM參照交代其實際量測表現。模型與訓練來源可追查，尺寸偏差及跨條件適用性則保留於相應範圍內解讀。
''')

write('00_Plan/REPLACEMENT_CHECKLIST.md','''# 改稿核對清單

- 本文只使用一個MOSR模型，實作身分為固定R129 step08192與80/16外框。
- 整段替換4.4架構、4.5資料、4.6訓練、5.4實作以及相關結果圖表；不能只全域取代V42字樣。
- 刪除原5.4.7、6.2.6消融內容、圖表及所有回指；不另名加回，不設待做消融章。
- 刪除內部模型選拔、外部模型排行與舊速度名次；不移往附錄重新堆入。
- 保留ACM粗輪廓、最大梯度取邊及LSC／尺寸／形狀的共同讀法。
- 光學、設備、參考文獻及正確量測定義大部分保留。
- 校正資料來源、前期初始化與接續訓練如實交代；不誤稱完全從零或SEM從未參與系統校正。
- 原圖與重建圖尺寸、顯示範圍、圖說一致；不把粗輪廓當最終邊界，也不把擬合圓當真形狀。
- 只使用修正後新九顆的主要结果，避免混入舊4.092nm、其他模型、W16或舊36顆不同倍率結果。
- R129與MOSR在資料表和正文的對應一致；不替其他模型圖改圖例冒充。
- 摘要、中英文摘要、結論與結果表數字一致；改善先呈現，必要限制簡短且數據完整。
- 原圖、平台與SEM是對照／參照，不作多模型競賽。
- 更新圖表編號、目錄、交叉引用與引用文獻；完成Word副本後逐頁檢查。

本次只備稿，Word仍是原稿副本，不能把「資料已備齊」寫成「論文已改寫完成」。
''')

# Compact source locator for full-size inputs intentionally kept in original locations.
plan=load(H/'04_Verification_and_Sources/config/plan.json');loc=[]
for f in plan['frames']:
 raw=Path(f['source']['path']);meta=R/f'Experiments/R136_PIRepeatability/results/R129/{f["run"]}/{f["index"]+1:02d}.json';o=load(meta);v=Path(o['values']['path'])
 assert raw.exists() and v.exists()
 loc.append(dict(run=f['run'],index=f['index'],raw_path=str(raw),raw_expected_sha256=f['source']['sha256'],reconstruction_path=str(v),reconstruction_expected_sha256=o['values']['sha256'],status='exists; expected hashes retained from source record, not all rehashed this preparation'))
pd.DataFrame(loc).to_csv(O/'07_Checks/full_image_sources_930.csv',index=False,encoding='utf-8-sig')
save('07_Checks/visual_review.json',dict(new_figures_reviewed=['F01','F02','F03','F04'],contour_start_end_redrawn_for_page_margins=True,remaining_curated_figures='Existing source figures previously reviewed; inspect final selected images again before sealing this package.',word_rendering='Not performed: unchanged original Word is reference material, not a rewritten deliverable.'))
write('06_Internal_Sources/README.md','''# 內部來源用途

這裡保留方法、訓練及初始化的原始程式／報告副本，用來核對方法，不是要放進論文的版本對照。原報告內部分相對連結仍屬原專案環境；請用07_Checks/source_copies.json找回其原位置。可直接用於本次撰稿的文字、表格與圖，在00_Plan、04_Results與05_Paper_Figures。

程式副本不是重新訓練的獨立環境。完整既有訓練套件仍在原位置；大型訓練陣列與完整影像以來源清單定位。原始檔案未被修改。
''')
write('START_HERE.md','''# R129單一模型論文：改寫計畫與備稿資料

已按最新決定備齊：**一個MOSR模型、保留ACM與Contour重點、抽換V42現用方法及結果、本次不寫消融。**

先讀 [完整改寫計畫](00_Plan/COMPLETE_REWRITE_PLAN.md)，再看 [圖表及圖說](00_Plan/FIGURES_AND_CAPTIONS.md)。[核心段落](00_Plan/WRITING_PASSAGES.md)可直接作改稿材料；[逐節處理表](00_Plan/section_action_map.csv)對應原稿全部131個標題。

| 資料夾 | 用途 |
|---|---|
| 01_Original_Thesis | 原Word完整副本與文字索引；尚未改寫 |
| 02_Method_and_Training | 固定最終模型、光學資料、實際訓練設定、8192步曲線與開發紀錄 |
| 03_Dataset | 768筆來源清單、分類數量、全部來源說明及7類實際訓練輸入範例 |
| 04_Results | 完整R129新九顆交接包，以及可放正文的六份表格 |
| 05_Paper_Figures | 10組圖：架構、資料、訓練、ACM、選區、位移、輪廓與SEM |
| 06_Internal_Sources | 方法／量測程式及初始化來源，只供核對，不堆入論文 |
| 07_Checks | 檔案來源、完整性、資料與訓練紀錄核對、完整影像位置 |

所有論文主要成果皆取自固定R129與相同Raw，不含R128／R61／V42效果排名。資料來源中的歷史名稱是追溯資訊，不是另一套正文模型。

768組完整訓練陣列與930張完整影像保留原位置，清單可定位；備稿使用的統計、範例、圖表與權重已收進本包。這是撰稿資料包，不是重新訓練環境。

**目前完成資料準備，沒有修改原Word，也沒有宣稱論文已改完。** 不必新增拍攝或消融才開始改稿。必要限制簡短留在對應表格及討論，沒有刪除原始資料。

執行verify_package.py可核對本包檔案。完整數據來源包另有自己的原始清單，保持不變。
''')

cp(Path(__file__),'07_Checks/finish_materials.py')
save('07_Checks/source_copies.json',copies)
print('Plan, captions, tables, passages and source locator prepared.',flush=True)
