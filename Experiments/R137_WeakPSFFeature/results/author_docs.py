from pathlib import Path
import ast,json,hashlib,shutil
import numpy as np,pandas as pd
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
PROJECT_ROOT = Path(__file__).resolve().parents[3]
R=Path(str(PROJECT_ROOT / 'Experiments/R137_WeakPSFFeature'));B=R.parent/'R130_Clean';P=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R137_WeakPSF_Web_Documents_20260922'));S=R/'results/comparison'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
t=load(R/'runs/formal_8192/training_complete.json');tables={p.stem:pd.read_csv(p) for p in S.glob('*.csv')};g=tables['shape_size_summary'];sem=tables['SEM_comparison']
colors={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722','R137-WeakPSF':'#198754'}
figs={p.stem:p for p in (P/'圖表').glob('*.png')};pillars=pd.read_csv(P/'完整數據/per_pillar_statistics.csv').to_dict('records');source=load(P/'來源與核對/SOURCE_COPIES.json')
explanation='2026年9月22日，使用者補充：這次較慢估計是 GPU 同時被另一個訓練程序佔用。此為使用者提出的可能原因；本輪沒有保存足以重建全程共用程度的 GPU 程序利用率時間序列，故不能量化影響，也不能證實所有時間差都由它造成。'

src=(B/'results/build_web_documents.py').read_text(encoding='utf-8-sig');node=next(n for n in ast.parse(src).body if isinstance(n,ast.ClassDef) and n.name=='Report');code=ast.unparse(node).replace('R130 Clean','R137 Weak PSF').replace('2026 09 20','2026 09 22').replace('2026年9月20日','2026年9月22日');exec(code)
def tab(x,df,title):x.table(df,title)
# 01 conditions
x=Report(1,'R137 實驗條件與訓練紀錄','本文件記錄已完成的弱 PSF 測試。目的在相同合成訓練與真實量測條件下，觀察 R130 加入弱光學特徵後的結果。使用既有25顆PSF、固定0.02特徵強度，從零訓練8192次。這不是重做PSF校準，也沒有自動取代論文或正式基準模型。')
x.h('實際比較條件');x.table(pd.DataFrame([
 ['主要比較','R130 Clean 與 R137 WeakPSF；Raw 和 R129 提供背景對照'],['共同訓練資料','512訓練／128開發／128既有生成測試母場景'],['共同訓練次數','8192更新，16循環，每循環512母場景'],['共同起始條件','主幹初始數值完全一致；均從零開始'],['R137新增','25顆PSF固定平均、光學線索、640個轉換參數'],['PSF固定強度','0.02，未依真實結果改動'],['參數數量','R130 300101；R137 300741'],['真實驗證','相同30趟×31位置，共930张；每張相同九顆'],['模型選擇','固定使用第8192次，未按真實結果挑選'],['速度条件','可能有其他訓練共用GPU，非受控效率比較']],columns=['項目','內容']),'同條件指資料、訓練與量測規則；不包含已控制GPU負載。')
x.h('模型如何使用 PSF');x.p('每顆101×101的PSF先各自正規化，再將25顆平均並正規化。它們是既有校準緩衝資料，沒有搬入舊神經網路權重。此次沒有經確認的25顆視野位置對應，故使用固定平均，不把它們自行排成5×5空間場，也沒有啟用原R129的四候選亮度統計權重網路。\n\n原圖維持0到1的灰階輸入。光學分支先鏡射延伸50像素，依PSF強度質心定義中心，使用正則值0.0565的Wiener形式，直流增益為1；扣除原圖得到光學修正線索。這個線索經3×3卷積轉成64通道，經tanh限制後乘0.02，加入主幹輸入卷積的特徵，再做SiLU。四次修正共用同一份光學特徵。\n\n0.02限制的是特徵注入，不代表最後影像必然只改變2%，也不能和R129輸入影像混合強度直接等同。原圖沒有被光學分支先強制替換。新轉換層初始為零，模型初始输出精確等於原圖；訓練後則不保證所有清楚影像都完全不變。')
x.h('原尺寸主幹與四次修正');x.p('主幹沿用七通道線索：目前重建、原圖、兩者之差、原圖水平差、垂直差、拉普拉斯差、5×5局部均值。先7轉64通道，再經四個雙3×3卷積殘差區塊，膨脹間距1、2、4、2，區塊殘差係數0.1，最後64轉1通道。四個回合共用網路，步幅初始0.05、上限0.25；建議修正僅經一次tanh，累積修正限制±0.35，輸出以原圖加累積修正並限制到0至1。\n\n神經主幹沒有上下採樣；本輪不能宣稱新增抗混疊上採樣。光學分支是全局運算，不能繼續稱整個模型只有有限局部影響；分塊時先求完整光學線索，再裁同一線索搭配96像素邊界與512像素核心。')
x.h('資料來源與損失');x.p('訓練沿用R130的source、noiseless、target三類合成配對陣列，不重新製造更有利資料；訓練每循環用相同種子重抽噪聲，開發與測試固定。每個母場景有兩個視圖和已知合成位移。原384影像先計算PSF線索，再取32至351的320影像；中央96至223的128×128區域用於監督。\n\n本輪沒有直接以真實拍攝、SEM輪廓或PI位移當訓練標籤。但繼承的PSF可能源於舊SEM校準，所以不能把整個光學先驗說成完全獨立於SEM。資料生成本來包含模擬模糊，這和模型讀取固定實測先驗是兩回事。\n\n總損失為影像項加0.2倍梯度項與0.2倍配對殘差項。穩健灰階誤差等於255乘以平均的平方根(e²加ε²)減ε，ε=0.5/255。梯度項為水平與垂直殘差差分；配對項對齊的是重建減目標的殘差，使用已知合成位移，有可觀測運動時才啟用。這個損失不是nm或PSNR。')
cfg=load(R/'config_r137_psf.yaml');x.table(pd.DataFrame([['優化器','AdamW'],['學習率','0.001至0.00001；128次暖身後餘弦下降'],['權重衰減','0.00001'],['梯度限制','5.0'],['隨機種子','模型1309001；順序1309002；噪聲1309003'],['數值設定','FP32，TF32關閉，確定性設定'],['開發檢查','第0次與每512次，共17次'],['前置試跑','另起32次模型，正式訓練前丟棄'],['硬體','NVIDIA RTX A6000'],['訓練實際經過秒數',f"{t['elapsed_seconds']:.6f}"],['訓練開始 UTC','2026-09-21 12:44:03'],['訓練完成 UTC','2026-09-21 14:35:05'],['全部流程完成 UTC','2026-09-21 16:44:57']],columns=['條件','實際設定或記錄']),'UTC加8小時為臺灣時間；全部流程在臺灣2026年9月22日00:44左右完成。時間不作獨占GPU效能宣稱。')
x.fig('training','R130與R137的訓練曲線和固定合成開發檢查，均沒有用真實結果選模型。')
rr=[]
for root,m in [(B,'R130'),(R,'R137')]:
 for name,label in [('dev_00000','初始開發'),('dev_08192','最終開發'),('test_08192','生成測試')]:
  v=load(root/'runs/formal_8192/evaluations'/(name+'.json'));rr.append([m,label,*[v['means'][k] for k in ['total','image','gradient','pair']]])
x.table(pd.DataFrame(rr,columns=['模型','資料','總損失','影像','梯度','配對']),'合成測試結果並非全都改善，不能只取真實指標的有利部分。')
x.h('可核對的執行身份');x.p('最終模型識別碼：'+t['final_checkpoint']['sha256']+'。本次整理另外核對全部8192次更新的母場景、輸入內容識別、噪聲、順序及學習率，與R130逐筆一致。模型多了光學轉換參數，因此仍不是只改一個數值的相同網路；單次訓練不能證明所有改善都由PSF物理資訊獨立造成。');x.finish()
#02 results
x=Report(2,'R137 真實影像比較結果','本文件列出本輪Raw、R129、R130、R137的全部主要比較。R137相對R130的短步位移、尺寸及輪廓重拍有小幅改善；尺寸偏差仍在，長距離位移沒有明確提升。四方法使用同一批930張影像，以下數字不能外推成跨樣本、跨曝光或完全獨立SEM確認。')
x.h('取樣和共同量測');x.p('30趟，每趟31位置，約1μm相鄰位移，使用PI實際回授。相同角落九顆，20×，1544×2064，曝光3000μs，固定172.5nm/px。先共用原圖追蹤種子，再以ACM和法線最大梯度得到64個邊界點，擬合最小平方圓。ACM13次、局部半寬14像素、法線半寬2.4、步距0.1、平滑0.65，暗物體極性。沒有按模型另調量測參數。\n\n位移先逐顆作圓心差，再對九顆x、y分量各取中位數，投影固定軸(−0.9998766245,0.0157078246)，乘尺度後减PI回授。相鄰為j減j−1；起點為j減0，不另扣一次位移。移動軸來自前6趟Raw，主表仍是全部30趟，並非全體均為獨立校準後驗證。')
x.fig('selected','青色所示角落九顆是本次實際取樣；橘色中央九顆為歷史位置，不混入本表。')
x.h('位移比較');d=tables['displacement_summary']
for kind,title in [('adjacent','相鄰位移'),('start','相對起點位移')]:
 z=d[d.kind==kind].drop(columns='kind').rename(columns={'model':'方法','mae_nm':'平均絕對差','bias_nm':'有號平均差','repeatability_nm':'重拍標準差','maximum_error_nm':'最大絕對差'});x.table(z,title+'，單位nm，每方法900筆。重拍值為30位置的各自30趟標準差再平均。')
x.fig('displacement','線為各位置平均有號差，陰影為±1重拍標準差，並非95%平均值區間。')
x.table(tables['endpoint_30um'].rename(columns={'model':'方法','mean':'平均差','std':'標準差','min':'最小差','max':'最大差'}),'約30μm終點的30趟統計，單位nm。')
x.h('尺寸與輪廓重拍');x.table(g[['model','diameter_mean_nm','diameter_repeat_sd_nm','diameter_repeat_absmax_nm']].rename(columns={'model':'方法','diameter_mean_nm':'平均直徑','diameter_repeat_sd_nm':'直徑重拍SD','diameter_repeat_absmax_nm':'最大重拍偏離'}),'單位nm；最大重拍偏離以同一顆同一位置的30趟平均為基準。')
x.table(g[['model','contour_repeat_sd_nm','shape_repeat_sd_nm']].rename(columns={'model':'方法','contour_repeat_sd_nm':'輪廓重拍SD','shape_repeat_sd_nm':'去尺寸形狀SD'}),'固定位置與顆粒先求跨30趟樣本變異數，再平均並開根號。輪廓置中但不縮放，形狀項另扣每圈平均半徑。')
x.fig('repeatability','小值代表重拍更一致，並不等於更接近SEM真值。')
x.h('SEM 尺寸與形狀');x.p('SEM參考平均直徑2614.438543257nm。完整徑向差保留大小差；去尺寸形狀差則雙方各自扣平均半徑。64個真實邊界點插值為720方向，插值不增加獨立樣本。兩方向候選的九顆集合相同，對應順序一為22,23,24,28,29,30,34,35,36，順序二為22,28,34,23,29,35,24,30,36，兩者都保留。')
for c in [1,2]:x.table(sem[sem.mapping_candidate==c][['model','mean_diameter_difference_nm','full_radial_difference_nm','de_size_shape_difference_nm']].rename(columns={'model':'方法','mean_diameter_difference_nm':'有號直徑差','full_radial_difference_nm':'完整徑向差','de_size_shape_difference_nm':'去尺寸形狀差'}),f'方向候選{c}，單位nm。')
x.fig('SEM','完整保留兩個方向候選；不能只選有利方向。樣本原本不完全圓，未以圓度越高越好作判定。')
x.h('整趟配對的差值範圍');ci=tables['paired_scan_intervals']
for ref in ['Raw','R129','R130-Clean']:
 z=ci[ci.reference==ref].drop(columns='reference');z['metric']=z.metric.replace({'adjacent_mae_nm':'相鄰平均絕對差','start_mae_nm':'起點平均絕對差','diameter_repeat_sd_nm':'直徑重拍SD','contour_repeat_sd_nm':'輪廓重拍SD','shape_repeat_sd_nm':'去尺寸形狀SD'});z=z.rename(columns={'metric':'指標','difference_nm':'R137減參考','ci95_low':'95%下界','ci95_high':'95%上界','improved_scans':'改善趟數'});x.table(z,'參考方法 '+ref+'；單位nm，負值表示R137較小。空白改善趟數不是零。')
x.p('以完整30趟配對重抽2000次，種子130136，取2.5與97.5百分位；九顆與720方向不當作獨立重拍。相對R130短步差值約−0.205nm，區間−0.307至−0.107nm，21/30趟改善。起點差值區間跨零，不能宣稱有明確進步。這是單次訓練與單工作階段的結果；本輪沒有另做R137時間區塊敏感度，也沒有直接沿用R130舊區間冒充新結果。');x.finish()
#03 optical & runtime
x=Report(3,'R137 光學作用與執行時間紀錄','本文件記錄PSF是否確實參與，以及本輪速度數字應如何解讀。開關PSF和零線索檢查支持光學分支確實有作用；速度則可能受到GPU共用影響，目前不足以比較模型固有快慢。')
x.h('前置檢查與最終核對');pre=load(R/'results/preflight.json');x.table(pd.DataFrame([['使用PSF數量',25],['固定特徵強度',.02],['獨立光學公式最大差',pre['optical_numpy_max_error']],['非中性分塊最大差',pre['full_tile_max_error']],['固定線索上下文最大差',pre['conditional_context_max_error']],['相對梯度差',pre['conditional_gradient_relative_error']],['最終分塊最大差',1.1920928955078125e-7]],columns=['檢查','數值']),'接近零的小數以完整原值見完整數據/preflight.json；Word六位顯示若為0不代表逐位元零。')
x.p('光學公式独立重算差5.7305×10⁻⁷；固定線索下相對梯度差1.1530×10⁻⁷；最終完整與分塊最大差1.1921×10⁻⁷，低於預设2×10⁻⁶。關閉光學或把強度設0時，光學計算會完全跳過。全局PSF線索本身沒有被宣稱是局部算子。\n\n最終檢查核對930張輸出內容識別、8192次更新和優化器步數，重新擬合8370圈最大差4.7807×10⁻⁷像素。後續另以四方法全部圓心重算7200筆位移，最大差3.5598×10⁻¹²nm。這些是執行與算術一致性的證據，不是獨立物理準確度的證明。')
act=pd.read_csv(R/'results/PSF_activity_real_examples.csv');x.h('四張固定實拍開關檢查');x.table(act[['frame','on_minus_off_rms_gray','on_minus_off_max_gray','actual_cue_vs_zero_rms_gray']].rename(columns={'frame':'全體索引','on_minus_off_rms_gray':'開關差RMS','on_minus_off_max_gray':'開關最大差','actual_cue_vs_zero_rms_gray':'實際對零線索RMS'}),'灰階以0到255表示。四張索引為0、30、899、929；對應第一趟及最後一趟的起點、終點，非挑有利影像。')
x.table(act[['frame','PSF_cue_rms','feature_rms','feature_max']].rename(columns={'frame':'索引','PSF_cue_rms':'光學線索RMS','feature_rms':'注入特徵RMS','feature_max':'注入特徵最大值'}),'特徵幅度均低於固定上限0.02；這是特徵值，不是尺寸或位移單位。')
x.fig('onoff','同一個最終模型的PSF開啟、關閉與原圖；差異很小仍可由數值確認。此圖不是兩個重新訓練模型的完整效果比較。')
z=pd.read_csv(R/'results/PSF_on_off_generated32.csv');x.h('生成資料的固定三十二組檢查');x.table(pd.DataFrame([['平均損失',z.on_loss.mean(),z.off_loss.mean()],['開啟減關閉',float((z.on_loss-z.off_loss).mean()),None],['開啟損失較小組數',int((z.on_loss<z.off_loss).sum()),None]],columns=['項目','開啟或差值','關閉']),'固定生成測試索引0到31。全部32筆未四捨五入數值附於統計細表及CSV。')
x.p('同權重關閉只能顯示該已訓練模型對光學分支的依賴，不能把它當作從零重訓的完整消融。本輪R137對R130的差異同時包含新增參數及訓練軌跡，因此不能宣稱全部收益已被證明只由PSF物理知識造成。')
x.h('GPU 共用情境補充');x.p(explanation+'\n\n因此，本輪計時只記錄「在當時條件下實際花多久」，不拿來當模型固有效率排名。不能再把R137約6.99秒、R130約1.38秒直接解讀成PSF使模型慢五倍，也不能反過來說排除共用後兩者一定一樣快。')
rt=pd.read_csv(R/'results/reconstruction_runtime.csv');x.table(pd.DataFrame([['R137 全部930張重建中位數',float(rt.total_reconstruction_seconds.median()),'包含光學與神經；負載未控制'],['R137 含讀寫中位數',float(rt.end_to_end_load_infer_save_seconds.median()),'包含載入和寫出'],['R130 歷史純神經中位數',1.38404875,'另一輪，未匹配共用條件'],['R130 歷史含讀寫中位數',1.86689665,'另一輪，未匹配共用條件']],columns=['記錄','秒每張','範圍']),'保留原值，不為推測GPU共用而改寫、扣除或校正時間。')
prof=load(R/'results/profile.json');x.table(pd.DataFrame(prof['records'])[['mode','repeat','seconds','allocated_bytes','reserved_bytes']].rename(columns={'mode':'模式','repeat':'次序','seconds':'秒','allocated_bytes':'配置位元組','reserved_bytes':'保留位元組'}),'另外的四次完整及分塊計時，亦無獨占GPU證明。保留記憶體受先前執行快取影響，不代表最低可用顯示卡容量。')
x.p('若未來需正式效率比較，才另外在受控GPU負載下，固定影像、精度、暖機與同步規則，交錯測兩模型，分開光學、神經與讀寫時間。本次依要求整理紀錄，沒有新增此項測試。');x.finish()
#04 reading & detailed pillar tables
x=Report(4,'R137 結果解讀與論文引用建議','本文件將已完成結果轉成論文可用的解讀，並附逐顆詳細數字。重點是正常拍攝下的LSC位移與ACM輪廓量測。保留原有結果及其限制，不把速度共用情境混成架構缺點，也不因為希望保留PSF創新而宣稱尚未完成的因果證明。')
x.h('目前可以下的結論');x.p('相對R130，R137短步平均絕對PI差由4.121476降至3.916681nm，改善約5.0%；尺寸重拍由16.421786降至14.262392nm，約13.1%；輪廓重拍由18.579026降至17.709881nm，約4.7%。相鄰重拍由4.184162降至3.905599nm，最大相鄰差由20.414296降至17.544931nm。這是小幅、具體的實用改善。\n\n平均直徑卻由2833.847223變成2836.821732nm，對SEM有號差由219.408680變成222.383188nm，略為增加。相對起點的平均差相近，而重拍標準差由9.971710變成10.238951nm；不能宣稱長距離全面更好。SEM去尺寸形狀方向一略差、方向二略好，不能只引用其中一個方向。\n\nR137對R129的短步平均差、尺寸重拍與輪廓重拍較小，但去尺寸形狀重拍16.201211仍高於R129的15.788824nm。未來只採一個模型寫正文是可行的寫作安排，並不要求宣稱所有指標都勝過所有版本。')
x.h('適合寫進方法章的設計');x.p('可描述為以原圖為基準、原尺寸共享迭代主幹，加上固定校準PSF導出的弱光學特徵。說清楚25顆是固定平均，不是已驗證空間變動PSF；光學特徵經局部轉換，以固定0.02注入，並具備可關閉的接口。\n\n不可直接沿用V42或R129的所有舊創新名稱：本輪沒有抗混疊上採樣，也沒有四候選全圖亮度統計權重網路。可以說處理步驟及資料來源可追溯，不可把中間結果能查看就稱成完整XAI。新穎性仍需正式文獻比較，本次文件不建立首次提出的主張。')
x.h('可採用的結果段落');x.p('在同一批30趟重拍顯微資料中，加入固定弱PSF特徵的模型，其相鄰位移平均絕對PI差為3.917nm，相較不含此分支的R130之4.121nm略低；尺寸與輪廓重拍標準差分別降至14.262與17.710nm。結果支持此版本在本次樣本及工作階段下改善部分量測穩定性。\n\n然而，平均直徑仍較SEM參考大約222.383nm，未改善尺寸真實度；相對起點位移也未呈現明確整體優勢。執行期間可能存在GPU共用，因此計時僅作環境紀錄，不據此判定光學分支的固有速度代價。')
x.h('主文與附件的安排');x.table(pd.DataFrame([['模型與訓練','文件01的實際結構、設定與曲線'],['共同驗證','文件02的九顆位置與量測規則'],['主要結果','正文可選Raw對最終單一模型；R130／R129對照留作選型依據'],['輪廓重拍與SEM','分開重複性、完整尺寸及去尺寸形狀；不以圓度高低判定'],['PSF作用','文件03的固定開關檢查，只作機制核對'],['速度','保留環境情境與原值，不作公平速度競賽'],['消融','本輪沒有完成全面重新訓練消融，不補寫因果結論']],columns=['部分','建議用法']),'不為本次整理新增大量不必要實驗，也不把歷史不同樣本的數字改名放入。')
x.h('每顆尺寸及輪廓詳細數字')
for m in colors:
 z=pd.DataFrame(pillars);z=z[z.model==m].drop(columns='model').rename(columns={'pillar_id':'顆粒','diameter_mean_nm':'平均直徑','diameter_sd_nm':'直徑SD','contour_sd_nm':'輪廓SD','shape_sd_nm':'形狀SD'});x.table(z,m+'，單位nm。每顆包含31個固定位置、每位置30趟。')
x.h('完整資料如何讀取');x.p('完整數據包含四方法33480筆圓量測、7200筆合成位移、240組逐位置位移、240組逐趟位移、36組逐顆幾何、124組逐位置幾何，以及全部930張執行時間。閱讀文字版05完整統計細表逐表保留CSV原值，可直接另上傳給網頁對話；大量逐筆主表另外提供CSV，不把數萬列擠成Word頁面。\n\n每方法30個輪廓點檔，points形狀31×9×64×2；radial_profiles是720方向的插值半徑。原始大影像與完整合成影像陣列未全部嵌入本包。三十二組生成開關檢查、四張實拍作用檢查、全8192次更新與所有開發檢查均保留。資料不是新獨立樣本，且不包含完整量測不確定度合成。');x.finish()
# Exact uploadable text appendix and inventory; avoids dependence on local paths.
appendix=['# R137 完整統計細表','以下保留未四捨五入CSV值。單位及計算方式見文件02。Raw為原圖；R130無PSF；R137為0.02弱PSF；R129為既有參考。adjacent是相鄰法，start是相對起點。SD是重拍標準差，區間不是完整系統不確定度。']
large={'all_circles','all_displacements','reconstruction_runtime'}
for q in sorted((P/'完整數據').glob('*.csv')):
 if q.stem not in large:appendix+=['## '+q.name,'```csv\n'+q.read_text(encoding='utf-8-sig')+'```']
(P/'閱讀文字版/05_完整統計細表.md').write_text('\n\n'.join(appendix),encoding='utf-8')
(P/'00_閱讀與上傳說明.md').write_text('''# R137 弱PSF實驗詳細文件

可先直接上傳01至04四份Word。圖表已嵌入，數值、方法和條件均有文字說明，不用讀本機路徑。

01是實驗條件與訓練紀錄；02是全部主要真實比較；03是PSF作用與GPU共用情境下的速度紀錄；04是論文解讀與逐顆細表。需要更多詳細數字時，另上傳閱讀文字版05完整統計細表，或完整數據內所需CSV。

速度特別注意：使用者認為另一個訓練程序佔用GPU可能造成較慢；沒有全程負載紀錄可以量化影響。不要據此宣稱R137固有速度更慢，也不要宣稱排除共用一定相同。原計時和量測數字未改動。

若接收端只讀到Word文字，請另提供圖表資料夾的PNG。ZIP用於打包傳遞，解壓後選擇文件上傳，不假設網頁端必定自動展開所有內容。要逐段改寫論文，請另上傳原論文。
''',encoding='utf-8')
save(P/'來源與核對/SOURCE_COPIES.json',source)
save(P/'來源與核對/training_comparability_check.json',dict(updates_compared=8192,matched_fields=['step','epoch','position','parent_id','parent_sha256','input_sha256','noise_seed','learning_rate'],neural_initialization_matched_by_preflight=True,speed_conditions_matched=False,GPU_concurrency_user_report='possible cause, not quantified',final_checkpoint_sha256=t['final_checkpoint']['sha256']))
shutil.copy2(__file__,P/'來源與核對/build_documents.py')
print(json.dumps(dict(folder=str(P),documents=[q.name for q in P.glob('*.docx')],figures=len(figs)),ensure_ascii=True))
