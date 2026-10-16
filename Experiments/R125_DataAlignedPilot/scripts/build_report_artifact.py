"""Reader-facing canonical Data Analytics report from completed R125 evidence."""
import csv,json,pathlib,datetime,sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    first=load(ROOT/'results/data_audit_v1.json');second=load(ROOT/'results/data_audit_v2.json')
    comparison=[]
    for version,audit in [('第一版',first),('修正版',second)]:
        for scene in audit['scenes']:
            comparison.append({'scene':scene['scene_id'],'version':version,'category':scene['category'],'rms_ratio':max(x['rms_over_declared_sigma'] for x in scene['operator_fit_per_view']),'p99_ratio':max(x['p99_abs_over_declared_sigma'] for x in scene['operator_fit_per_view']),'passed':len(scene['failures'])==0})
    (ROOT/'results/data_fit_comparison.json').write_text(json.dumps({'sources':['results/data_audit_v1.json','results/data_audit_v2.json'],'rows':comparison},indent=2),encoding='utf-8')
    with (ROOT/'results/real_comparison/sem_exposure_comparison.csv').open(encoding='utf-8-sig') as f:sem=list(csv.DictReader(f))
    semrows=[];semchart=[]
    for arm in ['A','B','C']:
        for seed,index in [(1235001,1),(1235002,2)]:
            rows=[x for x in sem if x['arm']==arm and int(x['seed'])==seed and int(x['step'])==64 and x['reference']=='global_pitch_matched']
            v={int(x['exposure']):float(x['median_pillar_change_vs_Raw_px']) for x in rows}
            semrows.append({'model':f'{arm}／起點{index}','normal':f'{v[13]:+.5f}','dark':f'{v[24]:+.5f}','scope':'36柱、兩個已使用曝光'})
            for exp,label in [(13,'正常曝光'),(24,'暗曝光')]:
                measured=next(x for x in rows if int(x['exposure'])==exp)
                semchart.append({'model':f'{arm}／{index}','arm':arm,'seed':seed,'exposure':label,'change_px':v[exp],'reference':'global_pitch_matched','step':64,'physical_objects':36,'minimum_common_profiles':int(measured['minimum_common_profiles']),'final_readout_px':float(measured['median_pillar_common_mae_px']),'Raw_readout_px':float(measured['median_pillar_Raw_mae_px']),'worst_object_readout_px':float(measured['worst_pillar_common_mae_px'])})
    photo=load(ROOT/'results/real_photometry_scope.json');env=photo['training_level_envelope'];photorows=[{'source':'64個訓練場景','dark_level':f"{env['low_gray']['minimum']:.1f}–{env['low_gray']['maximum']:.1f}",'bright_level':f"{env['high_gray']['minimum']:.1f}–{env['high_gray']['maximum']:.1f}",'contrast':f"{env['contrast_gray']['minimum']:.1f}–{env['contrast_gray']['maximum']:.1f}"}]
    for x in photo['real_summary']:photorows.append({'source':'實拍曝光'+str(x['exposure'])+'：36柱中位數','dark_level':str(int(x['median_low_gray'])),'bright_level':str(int(x['median_high_gray'])),'contrast':str(int(x['median_contrast_gray']))})
    title='資料接通後的小試跑：相容性修正了，真實效益尚未成立'
    sources=[{'id':'fit','label':'R125 第一版／第二版64場景資料審查及配對摘要','path':'results/data_fit_comparison.json'},{'id':'execution','label':'R125 獨立執行審查：384次更新、6組、216份實拍輸出','path':'results/execution_audit_independent_v2.json'},{'id':'real','label':'R125 全12模型共同人口SEM讀值與真實位移對照','path':'results/real_comparison/summary.json'},{'id':'photo','label':'R125 訓練亮暗設定與固定Raw平台讀值的範圍對照','path':'results/real_photometry_scope.json'},{'id':'training_ref','label':'R125 固定前六個訓練場景的事後接線診斷','path':'results/training_reference_diagnostic/summary.json'},{'id':'methods','label':'R125 已凍結方法、資料與模型規格','path':'reports/R125_METHODOLOGY.md'}]
    blocks=[
        {'id':'title','type':'markdown','body':'# '+title},
        {'id':'summary','type':'markdown','body':'## 這批資料只適合目前的限定試驗\n\n第一版不能直接訓練；修正格點表示與生成精度後，才通過原先的相容性要求。模型也已實際更新並接受真實影像對照，**目前沒有可靠的整體改善，不能直接擴大訓練或升級模型**。來源隔離與數值相容性成立，並不代表成像假設或實拍資料範圍已經足夠。'},
        {'id':'counts','type':'metric-strip','cardIds':['run_counts']},
        {'id':'fit_text','type':'markdown','sourceId':'fit','body':'## 原本失敗的場景保留，修正後全部通過同一限制\n\n64個場景、128個中央區域都重新核對，形狀、模糊、雜訊及位移條件沒有變簡單。最差均方根差異由設定雜訊尺度的0.818倍降至0.166倍，門檻仍是0.25倍；第99百分位仍使用1倍門檻。下圖固定列出第一版失敗的三個成像場景，並非事後挑選最有利例子。'},
        {'id':'fit_chart','type':'chart','chartId':'fit_chart'},
        {'id':'real_text','type':'markdown','sourceId':'real','body':'## 真實結果還不足以支持長訓練\n\nA不執行額外成像校正；B執行；C再加幾何要求。每組兩個起點，各64次更新，主要比較固定用最後一步。A在正常曝光略好，但暗曝光退步；B／C沒有顯示可靠改善。下表用相同Raw對齊和全12模型共同有效剖面，負值代表比Raw好，單位是像素。它是固定SEM參考的半對比讀值，尚不是完整輪廓或材料邊界認證。'},
        {'id':'sem_chart','type':'chart','chartId':'sem_chart'},
        {'id':'sem_table','type':'table','tableId':'sem_table'},
        {'id':'motion_text','type':'markdown','sourceId':'real','body':'## 位移讀法也暴露未校準假設的問題\n\n六個固定實拍影像對中，B／C有讀值不可靠或跳峰的情況，最大的Raw差異約12.47像素，且在訓練前就已存在。這不能說物體真的多移動了12.47像素；它說明這套假設成像加上目前讀法尚未可靠。所有低反應及失敗均保留，沒有換區域或剔除後宣稱成功。'},
        {'id':'photo_text','type':'markdown','sourceId':'photo','body':'## 訓練亮暗範圍還沒有涵蓋實拍\n\n訓練目標的明暗差約94–163灰階，而暗曝光實拍約20灰階。兩個曝光的亮暗平台也都在這批訓練設定包絡之外。這是事後追加的來源範圍診斷，沒有改動本輪資料或模型；訓練設定與實拍讀值的定義並不完全相同，因此它提示資料缺口，不能單獨證明唯一根因。'},
        {'id':'photo_table','type':'table','tableId':'photo_table'},
        {'id':'learning','type':'markdown','sourceId':'training_ref','body':'## 有更新參數，不等於已經學會修復\n\n追加檢查固定前六個訓練場景，初始與64次更新後的重建誤差沒有明顯下降。這只是六個已訓練場景的接線診斷，不能代表全部資料，也不用來選模型；但它使得「直接增加輪數就會成功」缺乏依據。'},
        {'id':'scope','type':'markdown','sourceId':'methods','body':'## 方法與可支持的範圍\n\n資料全由新程序生成，沒有讀取評估光學影像、SEM或教師答案。8倍精度生成對接4倍成像狀態，主要學習計算保留2倍格點；每筆抽樣、裁切、模型實際輸入及成像設定都有紀錄。原始640像素物理資料完整保留，只略去不影響中央128像素的多餘計算。\n\n本輪是64場景、六組各64次更新的小試跑，不是原先512場景的大比較。實拍面板只有六張完整影像與六組前兩張的固定區域；SEM為36柱、兩個曝光、兩套參考。它們都是已使用的開發資料，不能當成新的獨立樣品。'},
        {'id':'limits','type':'markdown','body':'## 現在還缺什麼\n\n真實儀器的光學與相機校準、材料邊界和光學讀法的對應、相位／暈圈／非高斯效應、獨立的實際位移及光學細節答案都尚未完成。現有小試也不足以否定整個架構。圖像與量測改善必須分開驗證，不能由訓練誤差、校準標記或完成紀錄代替。'},
        {'id':'next','type':'markdown','body':'## 下一步先修可學習性與真實範圍\n\n保留目前六組為研究對照，不升級。先在來源獨立的固定簡單例子確認目標確實可學，再擴充真實亮暗／對比範圍並獨立核對成像方式。所有新改動應另立版本，用同樣的實拍面板比較，不能重寫本輪失敗。'},
        {'id':'questions','type':'markdown','body':'## 接下來要回答的問題\n\n哪些真實成像條件能被現有光學模型描述？暗曝光的訊息是否足以支撐幾何修正？學習步驟為何在這次小預算下幾乎沒有降低參考誤差？哪些新的、來源獨立的光學／SEM配對能驗證真正的泛化？'}
    ]
    charts=[{'id':'fit_chart','title':'失敗場景的成像差異','subtitle':'三個原有困難場景在不放寬門檻下改善；數值越低越好。','type':'bar','dataset':'fit_failures','sourceId':'fit','encodings':{'x':{'field':'scene','type':'nominal','label':'原有場景'},'y':{'field':'rms_ratio','type':'quantitative','label':'均方根差異／設定雜訊尺度'},'color':{'field':'version','type':'nominal','label':'資料與表示版本'}},'options':{'grouping':'grouped'}},{'id':'sem_chart','title':'小試跑後相對Raw的SEM參考讀值','subtitle':'正常曝光與暗曝光的方向不同，不能用平均分數抵銷退步。','type':'bar','dataset':'sem_chart','sourceId':'real','encodings':{'x':{'field':'model','type':'nominal','label':'組別／起點'},'y':{'field':'change_px','type':'quantitative','label':'配對中位數差（像素）'},'color':{'field':'exposure','type':'nominal','label':'實拍條件'}},'options':{'grouping':'grouped'}}]
    tables=[{'id':'sem_table','title':'同一共同人口的實拍比較','subtitle':'每組兩個起點，36柱跨同一曝光；負值比Raw好。','dataset':'sem_rows','sourceId':'real','defaultSort':{'field':'model','direction':'asc'},'columns':[{'field':'model','label':'組別','type':'text'},{'field':'normal','label':'正常曝光差（px）','type':'text','movement':True},{'field':'dark','label':'暗曝光差（px）','type':'text','movement':True}]},{'id':'photo_table','title':'亮暗條件的範圍差異','subtitle':'訓練欄為目標設定範圍；實拍欄為36柱平台讀值的中位數，單位皆為灰階。','dataset':'photo_rows','sourceId':'photo','defaultSort':{'field':'source','direction':'asc'},'columns':[{'field':'source','label':'來源','type':'text'},{'field':'dark_level','label':'暗側','type':'text'},{'field':'bright_level','label':'亮側','type':'text'},{'field':'contrast','label':'明暗差','type':'text'}]}]
    artifact={'surface':'report','manifest':{'version':1,'surface':'report','title':title,'description':'已執行的資料修正、六組小試跑與真實場景限制','generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':sources,'cards':[{'id':'run_counts','dataset':'counts','sourceId':'execution','metrics':[{'label':'新場景','field':'scenes'},{'label':'模型起點組合','field':'runs'},{'label':'實際更新','field':'updates'},{'label':'實拍輸出','field':'real_outputs'}]}],'charts':charts,'tables':tables,'blocks':blocks},'snapshot':{'version':1,'status':'ready','datasets':{'fit_failures':[x for x in comparison if x['scene'] in ['scene_013','scene_020','scene_050']],'sem_rows':semrows,'sem_chart':semchart,'photo_rows':photorows,'counts':[{'scenes':64,'runs':6,'updates':384,'real_outputs':216}]}},'package_info':{'mode':'portable_html','readOnly':True}}
    # The bundled reader requires runnable query provenance for native assets.
    # Execute a transparent SQLite rendering adapter on the already-verified
    # rows; do not invent an SQL origin for the underlying Python analyses.
    db=ROOT/'results/report_snapshot.sqlite'
    if db.exists():raise FileExistsError('Report snapshot already exists; retain it and use a new report version')
    con=sqlite3.connect(db);con.row_factory=sqlite3.Row;source_map={}
    for name,rows in artifact['snapshot']['datasets'].items():
        fields=list(rows[0]);types=['REAL' if isinstance(rows[0][f],(float,int,bool)) else 'TEXT' for f in fields]
        definitions=', '.join('"'+f+'" '+t for f,t in zip(fields,types));table='report_'+name
        con.execute(f'CREATE TABLE "{table}" ({definitions})')
        con.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in fields)})',[tuple(row.get(f) for f in fields) for row in rows]);con.commit()
        query=f'SELECT * FROM "{table}" ORDER BY rowid'
        extracted=[dict(row) for row in con.execute(query)];artifact['snapshot']['datasets'][name]=extracted
        sid='render_'+name;source_map[name]=sid
        artifact['manifest']['sources'].append({'id':sid,'label':'R125已核對結果的報告查詢：'+name,'path':'results/report_snapshot.sqlite','query':{'engine':'sqlite','sql':query,'description':'Executed report-formatting query over verified Python output rows; underlying scientific analysis remains in the cited JSON/CSV and notebook.','tables_used':[table],'metric_definitions':'Values are retained from verified R125 results; this query does not fit models or redefine metrics.'}})
    con.close()
    for collection in ['cards','charts','tables']:
        for item in artifact['manifest'][collection]:item['sourceId']=source_map[item['dataset']]
    artifact['manifest']['charts'][1]['subtitle']='全局柱距參考下，正常與暗曝光方向不同；歷史參考也是相同方向。'
    artifact['manifest']['tables'][0]['subtitle']='全局柱距參考，36柱、同一共同人口；負值比Raw好。'
    artifact['manifest']['cards'][0]['metrics'][-1]['label']='實拍輸出份數'
    p=ROOT/'reports/R125_REPORT.artifact.json';p.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8');print(str(p))
if __name__=='__main__':main()
