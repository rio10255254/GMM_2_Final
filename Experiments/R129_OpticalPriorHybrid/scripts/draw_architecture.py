"""Publish an implementation-backed R129 diagram, including explicit gaps."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch

def main():
    assert load(ROOT/'results/organization/verification.json')['passed']
    fig,ax=plt.subplots(figsize=(13,10));fig.subplots_adjust(0,0,1,1)
    ax.set(xlim=(0,13),ylim=(0,10));ax.axis('off')
    plt.rcParams['font.sans-serif']=['Microsoft JhengHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    def box(x,y,w,h,title,body='',color='#eaf3f5'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.05,rounding_size=0.08',facecolor=color,edgecolor='#526573',linewidth=1.2))
        ax.text(x+w/2,y+h-.23,title,ha='center',va='center',fontsize=12,fontweight='bold',color='#223844')
        if body:ax.text(x+w/2,y+h/2-.14,body,ha='center',va='center',fontsize=10.5,color='#334b59',linespacing=1.5)
    def arrow(a,b,label=None):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=14,color='#526573',linewidth=1.4))
        if label:ax.text((a[0]+b[0])/2+.08,(a[1]+b[1])/2,label,fontsize=9,ha='left',va='center',color='#526573')
    ax.text(.4,9.55,'R129｜目前實際運作的架構',fontsize=22,fontweight='bold',color='#223844')
    ax.text(.4,9.15,'整理版：同一份權重、相同計算；一個模型反覆修正四次。沒有新增訓練或效能提升宣告。',fontsize=11,color='#526573')
    box(.4,7.85,2.65,.85,'原始顯微影像','單張灰階，原始尺寸')
    box(3.55,7.75,3.8,1.10,'① 實測光學融合','固定光學資料＋受限修正\n只在進入重建前處理一次')
    box(8.0,7.65,4.5,1.30,'預先保存的光學資料','25 個核的平均＋4 個候選\n候選選擇有運算，額外價值尚未證實','#fff2d8')
    arrow((3.1,8.25),(3.5,8.25));arrow((7.95,8.25),(7.4,8.25))
    box(3.55,5.50,5.65,1.60,'② 同一套重建程序，連續使用四次','邊緣、亮暗及目前修正結果 → 提出小幅改動\n每次含改善放大的處理，再更新內部影像\n內部處理至 4 倍網格；最後回到原始尺寸')
    arrow((5.45,7.7),(5.45,7.15))
    box(9.70,5.70,2.8,1.22,'可查看每一步','保存每次修正的副本\n不干預模型輸出','#f0eef8')
    arrow((9.25,6.30),(9.65,6.30))
    box(3.55,3.57,5.65,1.40,'③ 以原圖為基準形成輸出','提取重建細節 → 限制修改量 → 加回原圖\n依影像品質調整幅度，修正平均亮度\n這些限制不等於已證明位置一定正確')
    arrow((6.3,5.45),(6.3,5.02))
    ax.plot([1.72,1.72,3.48],[7.8,4.25,4.25],color='#526573',linewidth=1.4)
    arrow((3.16,4.25),(3.50,4.25));ax.text(1.88,5.4,'原圖保留路徑',rotation=90,ha='center',va='center',fontsize=10,color='#526573')
    box(3.55,2.18,5.65,.85,'④ 輸出端邊界保護','邊界保留原圖；輸出寬高不變','#eef3ec')
    arrow((6.3,3.52),(6.3,3.08))
    box(9.70,2.15,2.8,1.15,'外部實際量測','輪廓、尺寸、位移\nSEM 僅在對照端使用','#eef3ec')
    arrow((9.25,2.6),(9.65,2.6))
    box(.45,.37,12.0,1.15,'尚未接入／尚未證實：不畫成既有能力','專門依邊緣方向修正的分支；每一步完整的成像核對；獨立的不確定性估計\n現有資料只支持接入短測。新增功能須另做對照，不能沿用本次「輸出完全一致」結論。','#fff2d8')
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    for ext in ['png','svg']:
        p=out/f'R129_organized_architecture.{ext}';assert not p.exists();fig.savefig(p,dpi=170)
    plt.close(fig)
    save(ROOT/'results/organization/diagram_sources.json',dict(created_utc=now(),script=record(__file__),implementation=load(ROOT/'config/organization_plan.json')['organized_files'],verification=record(ROOT/'results/organization/verification.json'),figures=[record(out/f'R129_organized_architecture.{ext}') for ext in ['png','svg']],scope='Current implementation, not proposed future modules'))
    print('Architecture PNG and SVG created')

if __name__=='__main__':main()
