"""Transferable paper handoff with explicit completed scope and fixed-field grayscale views."""
from pathlib import Path
import json,shutil,sys,zipfile,re
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read,sha,save,MOSR_SOURCE,RECORD
import numpy as np,pandas as pd,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def build(partial=False,final=False,completed_only=False):
    assert sum([partial,final,completed_only])<=1
    scope='completed_models' if completed_only else 'full_benchmark' if final else 'available_real_partial' if partial else 'available_real'
    receipt=read(ROOT/'results'/scope/'complete.json')
    assert receipt['state']==('partial' if partial else 'complete')
    destination=ROOT/'reports'/('COMPLETED_MODELS_THESIS_HANDOFF' if completed_only else 'FINAL_BENCHMARK_THESIS_HANDOFF' if final else 'AVAILABLE_MODELS_STAGE_PROGRESS' if partial else 'AVAILABLE_MODELS_STAGE_COMPLETE')
    destination.mkdir(parents=True,exist_ok=True)
    real=ROOT/'reports'/('COMPLETED_MODELS_RESULTS.md' if completed_only else 'FINAL_BENCHMARK_RESULTS.md' if final else 'AVAILABLE_MODELS_PROGRESS.md' if partial else 'AVAILABLE_MODELS_REAL_RESULTS.md')
    speed=ROOT/'reports'/('COMPLETED_MODELS_EFFICIENCY.md' if completed_only else 'FINAL_BENCHMARK_EFFICIENCY.md' if final else 'AVAILABLE_MODELS_EFFICIENCY.md')
    efficiency=speed.read_text(encoding='utf-8')
    if completed_only:efficiency=efficiency.replace('外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。','六個已訓練外部模型與RAW、Wiener、MOSR共九方法的完整實拍比較已完成，效率與量測結果分開解讀；SwinIR已暫停，不列入排名。')
    elif final:efficiency=efficiency.replace('外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。','十個可執行方法的完整實拍比較已完成，效率與量測指標分開解讀；另外兩個官方後端阻礙方法只列原因，不算作完成。')
    elif not partial:efficiency=efficiency.replace('外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。','本階段七方法的完整實拍比較已完成，效率與量測指標分開解讀；後續未完成模型不在本階段排名。')
    text='# 已完成方法之論文比較交接\n\n'
    text+='本文件可連同最新論文交給網頁版對話。效率測試的七種方法均已完成；目前已完成930張實拍量測的方法為：'+ '、'.join(receipt['methods'])+'。\n\n'
    text+=('其他方法實拍量測仍在執行，未完成者不得填入推估數字或排名。\n\n' if partial else '本階段包括四個完成訓練的外部模型與RAW、Wiener、MOSR；不代表後續模型或整個外部benchmark均已完成。\n\n')
    text+='請依下列真實數據修改論文的比較表、效率段落、圖說與討論。保留實際訓練輪數差異、SEM不利結果、長距離限制與量測失敗。使用RAW、MOSR與外部方法名稱；不修改原模型、PSF、尺度、方向或既有量測，也不要將合成影像分數代替實拍位移結果。\n\n'
    text+=efficiency.replace('# 已完成模型的新重建效率比較','## 新效率結果',1)+'\n\n'+real.read_text(encoding='utf-8').replace('# 已完成模型之完整實拍驗證與效率比較','## 實拍結果與比較方法',1)
    if final:
        text=text.replace('效率測試的七種方法均已完成','效率測試的十種可執行方法均已完成').replace('本階段包括四個完成訓練的外部模型與RAW、Wiener、MOSR；不代表後續模型或整個外部benchmark均已完成。','本次包含七個完成訓練的外部模型與RAW、Wiener、MOSR；U-Net與MambaIRv2因官方後端阻礙未完成，原因完整保留，不計入已驗證數量。')
    if completed_only:
        text=text.replace('效率測試的七種方法均已完成','效率測試的九種方法均已完成').replace('本階段包括四個完成訓練的外部模型與RAW、Wiener、MOSR；不代表後續模型或整個外部benchmark均已完成。','本次包含六個已完成訓練的外部模型與RAW、Wiener、MOSR，完整彙整使用者指定的已完成模型範圍；SwinIR已暫停且未完成，不列入結果、不自動續訓。U-Net及MambaIRv2官方後端阻礙另列，不冒充完成。')
    if completed_only or final:
        source_text=(RECORD/'REPORT.md').read_text(encoding='utf-8')
        architecture=source_text.split('## 3 模型實際結構與參數',1)[1].split('## 4 訓練資料如何製作',1)[0]
        training=source_text.split('## 5 兩階段訓練設定及目標',1)[1].split('### 5.2 訓練過程及合成最後測試',1)[0]
        extra='\n## MOSR完整架構、理念與原訓練紀錄\n\n多尺度脈絡每張只計算一次並由三個原尺寸階段共用；三個階段的修正參數各自獨立，不能寫成同一完整U-Net／ResNet重跑四遍。第一階段從零訓練主體8192次，第二階段凍結主體再訓練光學擴充8192次；本次外部比較沒有再訓練MOSR。完整具體設定沿用以下已核對原紀錄。\n'+architecture+'\n### 原兩階段訓練設定與目標\n'+training
        extra=extra.replace('R152','MOSR').replace('R148v2','原主體')
        extra=re.sub(r'!\[[^\]]*\]\([^)]*\)','',extra)
        extra=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',extra)
        text+=extra
        test_rows=[]
        for method in receipt['methods']:
            metrics=read(ROOT/'results/synthetic'/(method+'.json'))['mean'] if method in ['RAW','Wiener','MOSR'] else read(ROOT/'runs'/method/'training_complete.json')['synthetic_test']
            test_rows.append({'method':method,**metrics})
        test_frame=pd.DataFrame(test_rows)
        target=destination/'data'/scope/'synthetic_test_summary.csv';target.parent.mkdir(parents=True,exist_ok=True);test_frame.to_csv(target,index=False,encoding='utf-8-sig')
        lines=['| 方法 | 核心PSNR dB | 核心SSIM | 整張PSNR dB |','| --- | ---: | ---: | ---: |']
        for row in test_frame.itertuples():lines.append(f'| {row.method} | {row.PSNR_core_dB:.6f} | {row.SSIM_core:.6f} | {row.PSNR_full_dB:.6f} |')
        text+='\n## 完整合成測試摘要\n\n固定128母場景、各4視圖；核心為共同96×96有效區域，整張為384×384。這些指標有合成清楚答案，不能將實拍RAW當作真值，亦不能把本表排名代替位移／輪廓結果。五項原MOSR任務指標只作共同評估診斷，外部模型的訓練目標依各自原規則。\n\n'+'\n'.join(lines)+'\n\n完整診斷與未四捨五入值在data/completed_models/synthetic_test_summary.csv。\n'
        if final:text=text.replace('data/completed_models/synthetic_test_summary.csv','data/full_benchmark/synthetic_test_summary.csv')
        guide='''# 九方法論文修改位置與交付檢查

請連同最新版論文與REPORT.md閱讀。原論文尚未修改；本次提供已完成九方法的真實結果與寫入位置。

| 建議位置 | 可使用內容 |
| --- | --- |
| 第4.7.4、4.7.5節 | 九個二維位移向量算術平均、固定方向投影、每趟30步樣本SD與30趟方差合併；核對原式4-15至4-17 |
| 摘要、第1.3、6.2.5、6.2.8、7.1、7.3、表7-1 | RAW/MOSR平均版數字8.781／4.273 nm、降低51.3%；PI MAE6.969／3.598 nm、降低48.4%；起點相對MAE區間跨零與終點限制保留 |
| 第6.2.8之後新增第6.3節 | 九方法整體比較；理念／來源／具體設定、各自一般訓練目標、固定共同資料／監督區域、實際輪數與合成驗證選權重 |
| 第6.3主要結果表 | 單趟波動合併SD、相鄰PI MAE、完整輪廓重複SD分欄；配對區間與30趟改善範圍另附，不做一個加權總分 |
| 第6.3補充幾何表 | 直徑重複SD、去尺寸形狀SD、兩種SEM尺寸參照、兩個固定輪廓方向；穩定性與準度分開 |
| 第6.3效率表／原表6-9 | 135次同條件測量；前向時間、GPU配置／保留峰值、整張／原有分塊；不要混入讀存檔或不同條件舊秒數 |
| 第7章比較討論 | MOSR兩項位移目標較低；輪廓對EDSR區間跨零；NAFNet／EDSR／Restormer去尺寸形狀較好、RAW SEM尺寸差較小；速度／記憶體不利結果保留 |
| 附錄與方法狀態 | 全部輪數、逐趟／逐步資料、所有區間、效率採樣、原生影像、錯誤與恢復；SwinIR標使用者暫停，另兩方法標官方後端阻礙 |

檢查：使用RAW／MOSR與正式方法名；方法整體比較不代表單一PSF／共享主幹／損失模組因果效果。九顆、30趟、930張全部保留；實拍、PI或SEM未用於挑設定／權重；不宣稱同訓練時間或全部充分收斂。根據配對區間改寫結論，不預寫MOSR所有指標最佳。

若網頁版不能讀ZIP，先上傳REPORT.md、本指南與最新版論文，再上傳figures內PNG／PDF及需要重畫的CSV。數字與圖都從附件取得，不從資料夾名稱推測結果。
'''
        if final:
            guide=guide.replace('九方法','十方法').replace('已完成九方法','已完成十方法').replace('135次同條件測量','150次同條件測量')
            guide=guide.replace('MOSR兩項位移目標較低；輪廓對EDSR區間跨零；NAFNet／EDSR／Restormer去尺寸形狀較好、RAW SEM尺寸差較小；速度／記憶體不利結果保留','依本次十方法完整數據與配對區間分項判讀；保留先前輪廓對EDSR區間跨零、形狀及SEM尺寸不利結果；SwinIR與其他方法的排名只由本次實測表決定')
            guide=guide.replace('SwinIR標使用者暫停，另兩方法標官方後端阻礙','SwinIR列實際8輪、合成驗證選用輪數及完整實拍結果；另兩方法標官方後端阻礙')
            guide+='\n已交付九方法的930張結果與135次效率直接重用，本次只新增SwinIR的930張／8370讀值與15次效率；九方法交接包保留原樣。\n'
        (destination/'PAPER_UPDATE_GUIDE.md').write_text(guide,encoding='utf-8')
    # Use a region chosen by the fixed efficiency protocol, rather than selecting by outcome.
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json');frame=plan['frames'][465]
    tracking=pd.read_csv(MOSR_SOURCE/'evaluation/tracking.csv');seed=tracking[(tracking.run==frame['run'])&(tracking['index']==frame['index'])&(tracking.pillar_id==5)][['seed_x_px','seed_y_px']].iloc[0].to_numpy()
    x,y=np.rint(seed).astype(int);half=24;bounds=(x-half,y-half,x+half,y+half)
    images=[]
    for method in receipt['methods']:
        if method=='RAW':image=cv2.imread(frame['source']['path'],cv2.IMREAD_UNCHANGED).astype(np.float32)/255
        else:
            source=(MOSR_SOURCE/'results/reconstruction'/frame['run']/f'{frame["index"]+1:02d}.npz') if method=='MOSR' else (ROOT/'results/reconstruction'/method/frame['run']/f'{frame["index"]+1:02d}.npz')
            with np.load(source,allow_pickle=False) as z:image=z['output']
        crop=image[y-half:y+half,x-half:x+half];assert crop.shape==(48,48)
        images.append(crop)
    columns=5 if final else len(images)
    rows=2 if final else 1
    fig,axes=plt.subplots(rows,columns,figsize=(7.2,3.3) if final else (1.5*len(images),1.8),squeeze=False)
    for ax,image,method in zip(axes.ravel(),images,receipt['methods']):
        ax.imshow(image,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(method,fontsize=9);ax.axis('off')
        ax.plot([4,4+1000/172.5],[43,43],color='white',linewidth=1.5);ax.text(4,40,'1 μm',color='white',fontsize=7)
    fig.tight_layout(pad=.3)
    for ext in ['png','svg','pdf']:
        p=destination/'figures'/('fixed_region_comparison.'+ext);p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p,dpi=300,bbox_inches='tight')
    plt.close(fig)
    np.savez_compressed(destination/'fixed_region_pixels.npz',crops=np.stack(images),methods=np.array(receipt['methods']),bounds_px=np.array(bounds))
    text+='''
## 同區域原生影像補充

![固定中央物件影像比較](figures/fixed_region_comparison.png)

圖說：固定第16趟起點的中央物件（第5顆）同座標48×48像素區域，各方法均使用同一原始影像與相同截取座標，比例尺1 μm（172.5 nm/pixel）。顯示共同固定0至1灰階範圍，不逐圖調整對比，不配準、縮放物件或後置銳化。像素放大僅為排版；量測使用原生浮點影像，未作顯示範圍裁切。區域取自原先固定三張效率影像之一，不依比較效果重新挑圖；此圖只是示例，正式指標使用全部930張。
'''
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if link=='figures/fixed_region_comparison.png':continue
        source=ROOT/'reports'/link;target=destination/link;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for directory in ['completed_efficiency' if completed_only else 'full_efficiency' if final else 'available_efficiency',scope]:
        for source in (ROOT/'reports/data'/directory).glob('*.csv'):
            target=destination/'data'/directory/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for name in ['NORMAL_TRAINING_PROTOCOL.json','TIME_BUDGET_OVERRIDE.json','official_sources.json','blocked_models.json']:
        target=destination/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'config'/name,target)
    if completed_only:shutil.copy2(ROOT/'config/COMPLETED_ONLY_SCOPE.json',destination/'provenance/COMPLETED_ONLY_SCOPE.json')
    if final and (ROOT/'config/USER_RESUME_20261006.json').exists():
        shutil.copy2(ROOT/'config/USER_RESUME_20261006.json',destination/'provenance/USER_RESUME_20261006.json')
        text+='\n## 九方法交付後之追加比較\n\n使用者在原九方法論文資料交付後直接要求續訓SwinIR，從原保存點接續至總共8輪；資料、模型與原訓練設定保持一致。原九方法的全部930張結果、8370讀值與135次效率測量直接重用，本次只新增SwinIR的930張、8370讀值及15次效率。本文件另行交付十方法結果，先前九方法資料包保持原樣。\n'
    if completed_only or final:
        failure=ROOT/'runs/completed_validation_logs/initial_driver_failure.json'
        if failure.exists():
            shutil.copy2(failure,destination/'provenance/USRNet_initial_driver_failure.json')
            text+='\n## 實際執行異常與恢復紀錄\n\nUSRNet-x1首次整張效率測試的程序曾在NVIDIA驅動nvcuda64.dll終止，Windows記錄0xc0000409。保存權重、資料、FP32精度與原生整張策略未改；隨後原生全尺寸八步前向檢查通過，相同三張影像各五次效率重測亦全部完成，正式表格僅使用完整成功的採樣。錯誤原因未被證明，不能寫成PSF或模型設計錯誤；原始程序及事件紀錄附於provenance。本次完整930張驗證結果與失敗覆蓋另列，不以先前程序退出掩蓋後續資料。\n'
    (destination/'REPORT.md').write_text(text,encoding='utf-8')
    save(destination/'provenance/scope.json',receipt)
    save(destination/'provenance/fixed_region.json',{'run':frame['run'],'index':frame['index'],'source_sha256':frame['source']['sha256'],'region_bounds_px':list(map(int,bounds)),
         'methods':receipt['methods'],'common_gray_range':[0,1],'region_selected_before_outcomes':True,'original_sources_modified':False})
    for link in re.findall(r'\]\(([^)]+)\)',text):assert (destination/link).is_file(),link
    assert not re.search(r'\bR(?:140|148|150|152|153)\b',text)
    manifest=[{'file':str(p.relative_to(destination)).replace('\\','/'),'sha256':sha(p),'bytes':p.stat().st_size}
              for p in sorted(destination.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
    save(destination/'MANIFEST.json',{'completed_scope':receipt['methods'],'all_seven_efficiencies_complete':True,'full_efficiency_method_count':len(receipt['methods']), 'full_stage_complete':not partial,'full_external_benchmark_complete':final,'completed_models_user_scope_complete':completed_only,'paused_methods':receipt.get('paused_methods',[]),'blocked_official_backends':receipt.get('blocked_official_backends',[]),'files':manifest})
    archive=destination.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(destination.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(destination.parent)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    save(ROOT/'results'/scope/'handoff_verified.json',{'state':'passed','archive':str(archive),'archive_sha256':sha(archive),'files':len(manifest)+1,'completed_scope':receipt['methods'],'full_stage_complete':not partial})
    print('PAPER HANDOFF PACKAGED',destination,flush=True)


if __name__=='__main__':build('--partial' in sys.argv, '--final' in sys.argv, '--completed-only' in sys.argv)
