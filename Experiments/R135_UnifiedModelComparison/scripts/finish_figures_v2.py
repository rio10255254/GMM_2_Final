from r135_common import *
from figures import render
import psutil,traceback,shutil
def main():
    while not (ROOT/'results/complete.json').exists():
        s=load(ROOT/'results/status.json')
        if s['phase']=='failed':return
        time.sleep(5)
    owner=load(ROOT/'results/status.json')['pid']
    while psutil.pid_exists(owner):
        try:
            if not any('continue_comparison' in x for x in psutil.Process(owner).cmdline()):break
        except psutil.NoSuchProcess:break
        time.sleep(1)
    render(ROOT/'reports/figures');report=ROOT/'reports/R135_RESULTS.md';shutil.copy2(report,ROOT/'results/report_before_figures.md');text=report.read_text(encoding='utf-8')
    text+='\n\n## 相同影像的比較圖\n\n![共同量測比較](figures/comparison.png)\n\n![固定同一顆pillar](figures/pillar18.png)\n'
    if (ROOT/'results/legacy_arithmetic/complete.json').exists():text+='\n舊V42的這次輸出採共同嚴格FP32計算。四張代表圖與歷史8bit影像最多差1灰階；允許舊式TF32近似時差異大幅縮小但未完全歸零。這次已逐張由原生推論程式驗證新共同設定，不冒充歷史PNG完全重播；算術敏感度對照另存於results/legacy_arithmetic。\n'
    text+='\nR61適配的兩次執行失敗另存results/failures：舊推論沒有外部原圖混合步驟，以及部分新比較影格沒有歷史R61檔可對照。修正只對齊原生推論與允許歷史參考不存在，仍重建全部201張；未修改R61權重或原始程式，未刪除量測失敗例子。\n'
    report.write_text(text,encoding='utf-8')
    gallery=REPO/'RECON_GALLERY.md'
    if gallery.exists():
        shutil.copy2(gallery,ROOT/'results/gallery_before.md');old=gallery.read_text(encoding='utf-8-sig');gallery.write_text(old+'\n\n## R135 含舊V42的統一精度比較\n\n固定同一顆pillar18、正常曝光14；舊V42有評估來源重疊，所有模型維持事先指定的使用設定。\n\n![同顆實拍比較](Experiments/R135_UnifiedModelComparison/reports/figures/pillar18.png)\n\n[共同量測結果](Experiments/R135_UnifiedModelComparison/reports/R135_RESULTS.md)\n',encoding='utf-8')
    registry=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(registry);entry=next(x for x in v['entries'] if x['id']=='r135_unified_comparison');entry.update(state='comparison_complete_no_promotion',actual_gib=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())/2**30);atomic(registry,v)
    verify();save(ROOT/'results/delivery_complete.json',dict(comparison=record(ROOT/'results/complete.json'),report=record(report),figures=[record(ROOT/'reports/figures'/n) for n in ['comparison.png','pillar18.png','verified.json']],no_promotion=True))
if __name__=='__main__':
    try:main()
    except BaseException:save(ROOT/'results/figure_failure.json',dict(error=traceback.format_exc()));raise
