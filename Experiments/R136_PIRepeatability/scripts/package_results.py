"""Portable reading/data package; no full acquisition images or model weights."""
from common import *
import shutil,csv,zipfile
import pandas as pd,numpy as np
BASE=ROOT/'output/R136_LSC_R61_Reading_Package'
TMP=ROOT/'tmp/package_build'
MAIN=ROOT/'results/lsc/r61_analysis'
TABLES=MAIN/'tables'
LABELS={'view':'分析範圍','model':'方法','kind':'位移方式','scans':'掃描次數','mae_nm':'平均絕對誤差(nm)','bias_nm':'平均有向誤差(nm)','repeatability_nm':'重拍波動(nm)','maximum_error_nm':'最大絕對誤差(nm)','run':'掃描識別','run_index':'掃描序號','index':'影格索引(0起)','pillar_id':'圓編號','center_x_px':'圓心X(px)','center_y_px':'圓心Y(px)','radius_px':'半徑(px)','seed_x_px':'粗定位X(px)','seed_y_px':'粗定位Y(px)','radial_rms_px':'圓邊界偏離(px)','gradient_median':'邊界梯度中位數','n':'筆數','rmse_nm':'平方平均根誤差(nm)','error_sd_nm':'掃描內誤差波動(nm)','max_abs_nm':'最大絕對誤差(nm)','transverse_rms_nm':'影像側向變動(nm)','time_block':'拍攝時段','position_index':'位置序號','pi_displacement_um':'PI平均位移(um)','repeatability_sd_nm':'重拍標準差(nm)','observed_min_nm':'觀察最小誤差(nm)','observed_max_nm':'觀察最大誤差(nm)','transverse_sd_nm':'側向重拍波動(nm)','pairs':'位移筆數','i':'起始影格(0起)','j':'終止影格(0起)','dx_px':'X位移(px)','dy_px':'Y位移(px)','pi_dx_um':'PI的X位移(um)','pi_dy_um':'PI的Y位移(um)','recorded_at':'拍攝時間(含時區)','radius_change_px':'半徑變化(px)','along_error_nm':'沿移動方向誤差(nm)','image_along_um':'LSC沿向位移(um)','error_nm':'相對PI誤差(nm)','transverse_nm':'影像側向位移(nm)','within_grid_sd_nm':'9圓位移不一致(nm)','time_block':'拍攝時段','image':'影像檔名','pi_x_um':'PI X位置(um)','pi_y_um':'PI Y位置(um)','exposure_us':'曝光時間(us)','frame':'相機影格號'}
VALUES={'nominal_all30':'全30次／名義尺度','nominal_late24':'後24次／名義尺度','calibrated_late24':'後24次／校正尺度','Raw':'原圖','adjacent':'相鄰每一步','start':'相對起點','early6':'前6次','late24':'後24次'}

def add_sheet(sheets,name,df,source):
    df=df.copy()
    for col in ['view','model','kind','time_block']:
        if col in df:df[col]=df[col].map(lambda x:VALUES.get(x,x))
    rows=df.astype(object).where(pd.notna(df),None).values.tolist()
    sheets.append(dict(name=name,headers=[LABELS.get(str(c),str(c)) for c in df.columns],keys=list(df.columns),rows=rows,source=source))

def prepare():
    BASE.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
    for p in ['01_報告','02_統計表/CSV','03_LSC圖表','04_補充_非LSC影像比對/CSV','04_補充_非LSC影像比對/圖表','05_定位與分析紀錄/邊界點','05_定位與分析紀錄/程式','05_定位與分析紀錄/PI原始紀錄']:(BASE/p).mkdir(parents=True,exist_ok=True)
    links=[]
    def copy(src,dest):
        src=Path(src);dest=BASE/dest;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);assert sha(src)==sha(dest);links.append(dict(package_path=dest.relative_to(BASE).as_posix(),source=str(src),sha256=sha(dest)))
    for f in TABLES.glob('*'):copy(f,Path('02_統計表/CSV')/f.name)
    for f in (ROOT/'reports/lsc_r61_figures').glob('*'):copy(f,Path('03_LSC圖表')/f.name)
    copy(ROOT/'reports/R136_LSC_R61_RESULTS.md','05_定位與分析紀錄/原分析報告.md')
    for f in (ROOT/'results/r61_analysis/tables').glob('*.csv'):copy(f,Path('04_補充_非LSC影像比對/CSV')/f.name)
    for f in (ROOT/'reports/r61_figures').glob('*'):copy(f,Path('04_補充_非LSC影像比對/圖表')/f.name)
    copy(ROOT/'reports/R136_R61_RESULTS.md','04_補充_非LSC影像比對/原分析報告.md')
    for name in ['verification.json','aggregate_crosscheck.json','visual_review.json','key_results.json','delivery_complete.json']:copy(MAIN/name,Path('05_定位與分析紀錄')/name)
    for name in ['plan.json','lsc_plan.json']:copy(ROOT/'config'/name,Path('05_定位與分析紀錄')/name)
    copy(ROOT/'results/lsc/tracking.csv','05_定位與分析紀錄/圓形目標追蹤.csv')
    for model in ['Raw','R61']:
        for f in (ROOT/'results/lsc/centers'/model).glob('*.npz'):copy(f,Path('05_定位與分析紀錄/邊界點')/model/f.name)
    for name in ['common.py','lsc_core.py','lsc_prepare.py','lsc_measure.py','analyze.py','lsc_details.py','lsc_publish.py']:copy(ROOT/'scripts'/name,Path('05_定位與分析紀錄/程式')/name)
    copy(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py','05_定位與分析紀錄/程式/reference_circle_core.py')
    plan=load(ROOT/'config/plan.json')
    for run in plan['runs']:copy(run['positions']['path'],Path('05_定位與分析紀錄/PI原始紀錄')/(run['run']+'.csv'))
    frames=pd.DataFrame([{k:f[k] for k in ['run_index','run','index','image','pi_x_um','pi_y_um','recorded_at','frame','exposure_us']} for f in plan['frames']]);frames.to_csv(BASE/'02_統計表/CSV/pi_feedback_all930.csv',index=False,encoding='utf-8-sig')
    save(BASE/'05_定位與分析紀錄/source_copy_manifest.json',dict(source_root=str(ROOT),files=links,note='Sources retained; copies checked by SHA256. Historical paths are provenance, not portable runtime requirements.'))
    save(TMP/'package_context.json',dict(package=str(BASE),created_utc=now(),R129_status_snapshot=load(ROOT/'results/status_R129.json'),scope='Raw/R61 complete LSC reading results;R129 not included'))
    sheets=[]
    guide=pd.DataFrame([
        ['本冊範圍','原圖與R61的完整LSC圓心位移結果；R129仍在運算，本版不納入。'],
        ['拍攝資料','2026-09-03，100MF，Basler acA2040-120um，20倍。30次掃描，每次31張。'],
        ['主量法','每張追蹤同一組9顆圓，LSC定位後相減；9顆位移分別取X、Y中位數。'],
        ['資料筆數','每方法930張、8370個圓心、900段相鄰位移、900筆起點相對位移。'],
        ['單位','nm為奈米，um為微米，px為像素。表中數字保留完整精度，顯示位數可自行調整。'],
        ['全30次','名義尺度0.1725um/px；主要比較使用相同方向。'],
        ['後24次','前6次原圖LSC與PI校正尺度及方向，固定用在後24次兩種方法。'],
        ['重拍波動','同一位置30次誤差的標準差，再對位置取平均；不是30次平均值的不確定度。'],
        ['95%範圍','以完整掃描重抽樣10000次；不是900段互相獨立的實驗，也不是單次未來量測保證。'],
        ['原始表','各表來源見02_統計表/CSV；本冊將部分欄位翻成中文並保留數值。'],
        ['閱讀建議','先看主要結果、各指標範圍與配對改善；再查每次掃描、各位置、各顆圓。'],
        ['適用範圍','只支持本批同樣品、同拍攝工作階段和LSC流程；完整不確定度仍需PI等校正資料。'],
        ['影像比對補充','04_補充_非LSC影像比對是另一種讀法；不能與主LSC數字混用。'],
        ['模型與影像','本包不含全量照片、重建影像或模型權重。含全部統計、圓心、位移和邊界點。'],
    ],columns=['項目','內容']);add_sheet(sheets,'閱讀指南',guide,'本包閱讀說明')
    add_sheet(sheets,'主要結果',pd.read_csv(TABLES/'readable_lsc_summary.csv'),'readable_lsc_summary.csv')
    sr=pd.read_csv(TABLES/'summary.csv');records=[]
    names={'bias_nm':'有向偏差','mae_nm':'平均絕對誤差','rmse_nm':'平方平均根誤差','error_sd_nm':'單次內誤差波動','max_abs_nm':'單次最大誤差','transverse_rms_nm':'影像側向變動'}
    for _,r in sr.iterrows():
        for k,n in names.items():records.append({'view':r['view'],'kind':r['kind'],'model':r['model'],'指標(nm)':n,'平均值':r[k+'_mean'],'次間標準差':r[k+'_sd_between_scans'],'平均值95%下限':r[k+'_ci95_low'],'平均值95%上限':r[k+'_ci95_high']})
    add_sheet(sheets,'各指標範圍',pd.DataFrame(records),'summary.csv')
    for name,file,columns in [
        ('配對改善','paired_comparisons.csv',['view','kind','candidate','reference','metric','paired_scans','candidate_minus_reference_mean_nm','ci95_low','ci95_high','block3_ci95_low','block3_ci95_high','improved_scans','worsened_scans']),
        ('每次掃描','per_scan.csv',None),('各位置波動','per_position.csv',None),('各顆圓','individual_circle_summary.csv',None),('兩個拍攝時段','time_blocks.csv',None),('最差案例','largest_errors.csv',['view','model','run_index','kind','i','j','pi_dy_um','image_along_um','error_nm','abs_error_nm']),
        ('全部圓心','all_circle_centers.csv',None),('逐顆圓位移','all_individual_circle_pairs.csv',['model','run_index','kind','i','j','pillar_id','dx_px','dy_px','pi_dx_um','pi_dy_um','along_error_nm','radius_change_px']),
        ('九圓合併位移','all_measurements.csv',['view','model','run_index','kind','i','j','pi_dy_um','dx_px','dy_px','image_along_um','error_nm','within_grid_x_sd_px','within_grid_y_sd_px']),('九圓間差異','within_grid_variation.csv',None)]:
        df=pd.read_csv(TABLES/file)
        if name=='九圓合併位移':df=df[df.view=='nominal_all30']
        if columns:df=df[columns]
        add_sheet(sheets,name,df,file)
    add_sheet(sheets,'PI原始回授',frames,'pi_feedback_all930.csv')
    save(TMP/'workbook_data.json',dict(sheets=sheets))
    print('Prepared reading package; workbook sheets',len(sheets),'source copies',len(links),flush=True)

def archive():
    items=[]
    for p in sorted(BASE.rglob('*')):
        if p.is_file() and p.name!='PACKAGE_MANIFEST.json':items.append(dict(path=p.relative_to(BASE).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    save(BASE/'PACKAGE_MANIFEST.json',dict(created_utc=now(),files=items,file_count=len(items),total_bytes=sum(x['bytes'] for x in items),scope='Reading and complete statistical results; no full capture or reconstruction image series'))
    target=BASE.with_suffix('.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in BASE.rglob('*'):
            if p.is_file():z.write(p,BASE.name+'/'+p.relative_to(BASE).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for item in items:
            data=z.read(BASE.name+'/'+item['path']);assert hashlib.sha256(data).hexdigest()==item['sha256']
    save(ROOT/'output/package_delivery.json',dict(archive=record(target),package=str(BASE),files=len(items)+1,total_bytes=sum(x['bytes'] for x in items),verified=True,completed_utc=now()))
    print('Verified ZIP',str(target),'MiB',round(target.stat().st_size/2**20,2),flush=True)

if __name__=='__main__':
    if '--archive' in sys.argv:archive()
    else:prepare()
