from common import *
import re,shutil
LABELS={'qualifying':'保留精度的完整驗證進行中','not_admitted':'保留精度的完整驗證未通過；沒有啟動長訓練','building_package':'完整驗證通過；獨立訓練包製作中','package_preflight':'獨立訓練包實測中','manual_control_test':'實際測試開始、暫停與續訓','long_training':'独立包長訓練進行中','paused':'長訓練已安全暫停','final_comparison':'長訓練完成；最終201張比較中','complete':'保留精度版本長訓練及最終比較完成，尚未採用為正式模型','failed':'保留精度版本執行遇到錯誤，未宣告完成'}
def publish():
    state=load(P/'results/status.json');label=LABELS[state['phase']];repo=E.parent.parent;report=E/'reports/R134_PRECISION_REVALIDATION.md';history=P/'results/index_history'/str(time.time_ns());history.mkdir(parents=True)
    for p in [report,repo/'PROJECT_STATE.md',repo/'ESTIMATOR_POLICY.json',repo/'Experiments/INDEX.md']:
        if p.exists():shutil.copy2(p,history/p.name)
    lines=['# R134 P1：保留量測精度的完整驗證與訓練','',label+'。','',f"目前記錄：{state['utc']}。",'',
    '這次只修正輸出與量測精度，模型和訓練條件未變。模型原本的浮點結果以無損檔案保存，重新讀回後才量測；一般灰階圖另作看圖副本。SEM的光學裁切也保留正規化後的精細值，Raw與A/C兩起點全部使用同一方式；SEM參考影像、座標、比例及輪廓算法保持固定，沒有重設材料真值。', '',
    '先前256階結果及未通過判定完整保留；這一輪是診斷後的新開發比較，不是未看過的確認集。生成開發及清楚影像驗證沿用原來的浮點訓練計算結果；起點仍由原本開發誤差選出的1342001，沒有依新的實拍結果改選。', '',
    '驗證包括：C選定起點全部201張；A兩起點及另一C起點各24張，重新比較原先12對；Raw與A/C兩起點各3張正常SEM、36顆。共273次完整位移影像重建，每張看圖副本都必須逐像素重現舊輸出，以確認網路本身沒有改。判定沿用原門檻；保存數值和預覽不能混用。', '',
    '正式開始長訓練的條件：新的雙起點SEM、12對及201張檢查全部通過；此版本先單獨打包，實際核對資料、搬移重建、儲存讀回、短跑暫停續訓及初始量測一致後，再延續8192次訓練。結束後另做全部201張高精度比較。原模型與8bit判定不覆寫，不自動更換正式模型。B/D獨立材料／光學校準仍未完成。']
    for folder,title in [('sem','SEM'),('motion','位移')]:
        p=P/f'results/{folder}/complete.json'
        if p.exists():
            v=load(p);lines+=['',f"{title}驗證：{'通過' if v['passed'] else '未通過'}。"]
            checks=v.get('checks',[])+v.get('full201_checks',[])+v.get('matched12_checks',[])
            for c in checks:
                if not c['passed']:lines.append('- 未通過：'+str(c))
    if state.get('package'):lines+=['','獨立訓練包：`'+state['package']+'`。']
    if state.get('error'):lines+=['','錯誤記錄：','```',state['error'],'```']
    final=P/'results/final_full201/complete.json'
    if final.exists():
        v=load(final);lines+=['',f"最終完整201張已完成；沿用原條件的結果：{'全部符合' if v['all_original_tolerances_met'] else '仍有未符合項目'}。這是開發結果，未自動採用。"]
        for c in v['checks']:
            if not c['passed']:lines.append('- 最終未符合：'+str(c))
    lines+=['','來源：`precision_revision/config/protocol.json`；目前狀態：`precision_revision/results/status.json`；位移進度：`precision_revision/results/motion/status.json`；實際套件測試：`precision_revision/results/operations/`。'];report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    p=repo/'ESTIMATOR_POLICY.json';v=load(p);x=next(x for x in v['open_side_tracks'] if x.get('candidate_id')=='R134_direct_state');x.update(precision_revision_status=state['phase'],precision_revision_report=report.relative_to(repo).as_posix(),original_admission_preserved=True,model_promoted=False);atomic(p,v)
    p=repo/'PROJECT_STATE.md';text=p.read_text(encoding='utf-8-sig');text=re.sub(r'(?m)^Last updated:.*$',f'Last updated: 2026-09-15（R134 P1：{label}）',text,count=1)
    notice=f'**R134 P1：** {label}。[保留精度驗證](Experiments/R134_DirectStateRepair/reports/R134_PRECISION_REVALIDATION.md)。原8bit未通過判定保留，新版本需全部合格並單獨打包實測才長訓練。'
    if '**R134 P1：**' in text:text=re.sub(r'(?m)^\*\*R134 P1：\*\*.*$',notice,text,count=1)
    else:text=text.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+notice,1)
    marker='### R134 complete full201 screening, not admitted (2026-09-15)'
    if '<!-- R134P1_START -->' in text:text=re.sub(r'<!-- R134P1_START -->.*?<!-- R134P1_END -->','<!-- R134P1_START -->\n'+notice+'\n<!-- R134P1_END -->',text,flags=re.S,count=1)
    else:text=text.replace(marker,marker+'\n\n<!-- R134P1_START -->\n'+notice+'\n<!-- R134P1_END -->',1)
    p.write_text(text,encoding='utf-8')
    p=repo/'Experiments/INDEX.md';text=p.read_text(encoding='utf-8-sig');text=re.sub(r'(?m)^\| R134 .*$',f'| R134 直接影像狀態修正 | [保留精度驗證](R134_DirectStateRepair/reports/R134_PRECISION_REVALIDATION.md) | {label}；原8bit判定保留；未升級 |',text);p.write_text(text,encoding='utf-8')
if __name__=='__main__':publish()
