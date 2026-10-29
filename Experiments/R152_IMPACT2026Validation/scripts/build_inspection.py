"""Evidence browser and full-field figures for the already completed experiment."""
from pathlib import Path
import sys,json,hashlib,html
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'inspection';ASSETS=OUT/'images'
ASSETS.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
PROJECT_ROOT = Path(__file__).resolve().parents[3]
backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
SEQS=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']
LABELS=['50×／0.5 μm','50×／1.0 μm','20×／0.5 μm','20×／1.0 μm']
METHODS=['Raw','Wiener','R152']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def display_png(a,p):Image.fromarray(np.rint(np.clip(a,0,1)*255).astype(np.uint8)).save(p)
def main():
    conf=load(ROOT/'sources/sequence_config.json');selection=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');manifest=pd.read_csv(ROOT/'results/raw_frame_manifest.csv').set_index(['sequence','frame_index'])
    pairs=pd.read_csv(ROOT/'results/full120/per_pair.csv');centers=pd.read_csv(ROOT/'results/full120/centers.csv')
    fig,axes=plt.subplots(4,2,figsize=(13,15),gridspec_kw={'width_ratios':[1.75,1]})
    firstfig,firstaxes=plt.subplots(4,2,figsize=(8,13))
    data=[];frame_total=0
    for si,(seq,label) in enumerate(zip(SEQS,LABELS)):
        s=conf['sequences'][seq];mag=s['magnification'];folder='20x' if mag=='20x' else '50x_calibrated';chosen=selection[selection.sequence==seq].reset_index(drop=True)
        frameids=sorted(set(chosen.start_frame_index)|set(chosen.end_frame_index));pitch=s['pitch_px'];margin=int(np.ceil(.55*pitch))
        psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf'];frames={};sample_raw={};sample_roi={}
        for fi in frameids:
            source=Path(PROJECT_ROOT / s['raw_dir'])/f'frame_{fi:04d}.bmp';assert sha(source)==manifest.loc[(seq,fi),'sha256']
            raw=backend.load_grayscale(source);assert raw.shape==(1536,2048)
            pred=backend.session_prediction(seq,int(fi),np.array(s['centers'],float),s['expected_signed_dx_px'])
            x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1)
            y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
            roi=raw[y0:y1,x0:x1]
            npz=ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz';receipt=load(npz.with_suffix('.json'));assert sha(npz)==receipt['output_sha256']
            r152=np.load(npz)['output'][y0:y1,x0:x1]
            wiener=backend.wiener_contrast_restore(roi,psf,backend.NSR,pitch_px=pitch)
            stem=f'{si}_{fi:04d}';imgs={}
            for m,a in zip(METHODS,[roi,wiener,r152]):
                p=ASSETS/f'{stem}_{m}.png';display_png(a,p);imgs[m]='images/'+p.name
            full=ASSETS/f'{stem}_field.jpg'
            im=Image.open(source).convert('L');im.thumbnail((1024,768));im.save(full,quality=92)
            c=centers[(centers.sequence==seq)&(centers.frame_index==fi)&(centers.method=='Raw')]
            frames[str(fi)]=dict(index=int(fi),source=str(source),shape=[2048,1536],roi=[x0,y0,x1,y1],images=imgs,full='images/'+full.name,centers=[[int(r.pillar_id),float(r.lsc_center_x_px),float(r.lsc_center_y_px)] for r in c.itertuples()])
            if fi in (int(chosen.iloc[0].start_frame_index),int(chosen.iloc[0].end_frame_index)):sample_raw[int(fi)]=raw;sample_roi[int(fi)]=(x0,y0,x1,y1)
            frame_total+=1
        p0=chosen.iloc[0];fi=int(p0.start_frame_index);raw=sample_raw[fi];x0,y0,x1,y1=sample_roi[fi]
        ax=axes[si,0];ax.imshow(raw,cmap='gray',vmin=0,vmax=1);ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,color='#f05c36',lw=1.8));ax.set_title(f'{mag} / {s["nominal_step_um"]:.1f} um | frame {fi:04d} | full input',fontsize=12);ax.set_axis_off()
        ax=axes[si,1];ax.imshow(raw[y0:y1,x0:x1],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title('The nine measured pillars',fontsize=12);ax.set_axis_off()
        for pid,cx,cy in frames[str(fi)]['centers']:ax.text(cx-x0,cy-y0,str(pid),ha='center',va='center',color='#f0c96b',fontsize=10)
        h,w=(y1-y0,x1-x0);bar=2/s['object_um_per_px'];ax.plot([w-5-bar,w-5],[h-6,h-6],color='white',lw=3);ax.text(w-5-bar/2,h-8,'2 um',ha='center',va='bottom',color='white',fontsize=9)
        # The same global crop for before and after preserves the visible displacement.
        start,end=int(p0.start_frame_index),int(p0.end_frame_index)
        boxes=[sample_roi[start],sample_roi[end]];bx0=min(b[0] for b in boxes);by0=min(b[1] for b in boxes);bx1=max(b[2] for b in boxes);by1=max(b[3] for b in boxes)
        for j,k in enumerate([start,end]):
            ax=firstaxes[si,j];ax.imshow(sample_raw[k][by0:by1,bx0:bx1],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.axis('off');ax.set_title(f'{mag} / {s["nominal_step_um"]:.1f} um | {"before" if j==0 else "after"} {k:04d}',fontsize=10)
        plist=[]
        for rank,row in chosen.iterrows():
            values=pairs[(pairs.sequence==seq)&(pairs.pair_rank_raw_locked==rank+1)]
            plist.append(dict(rank=rank+1,start=int(row.start_frame_index),end=int(row.end_frame_index),time_start=row.start_timestamp,time_end=row.end_timestamp,gap_seconds=float(row.gap_seconds),metrics=[dict(method=r.method,step_nm=r.measured_step_um*1000,nominal_error_nm=r.nominal_abs_error_nm,within_nm=r.within_grid_sd_nm) for r in values.itertuples()]))
        data.append(dict(sequence=seq,label=label,scale=s['object_um_per_px'],nominal=s['nominal_step_um'],frames=frames,pairs=plist,original_frames=s['frame_count'],unique_frames=len(frameids)))
        print('Prepared image evidence',label,len(frameids),flush=True)
    fig.suptitle('Actual input fields and the fixed nine-pillar measurement area',fontsize=18,weight='bold',y=.99);fig.subplots_adjust(top=.95,bottom=.02,left=.025,right=.98,hspace=.22,wspace=.04);fig.savefig(OUT/'full_fields_and_targets.png',dpi=220);plt.close(fig)
    firstfig.suptitle('First locked pair in each condition\nRaw images at identical global crop coordinates',fontsize=15,weight='bold',y=.99);firstfig.subplots_adjust(top=.92,bottom=.02,left=.03,right=.97,hspace=.23,wspace=.05);firstfig.savefig(OUT/'first_pairs_same_window.png',dpi=220);plt.close(firstfig)
    (OUT/'data.js').write_text('window.EXPERIMENT_DATA = '+json.dumps(data,ensure_ascii=False,allow_nan=False)+';\n',encoding='utf-8')
    assert frame_total==166 and sum(len(d['pairs']) for d in data)==120
    design='''# 本次實驗使用的影像、設計與具體設定

這份說明只描述已完成的原四組120配對實驗，不把R152另一批930張／30趟平台回授驗證混進來。來源是本工作區已鎖定的影像、配對、量測程式及輸出收據。

## 看圖入口

- [逐組影像瀏覽器：可選120組配對、前後影格及三方法](image_browser.html)
- [完整輸入畫面與實際九顆位置](full_fields_and_targets.png)
- [四組首對影像：前後使用相同畫面座標](first_pairs_same_window.png)
- [四條件三方法影像對照](../poster_assets/full120/03_representative_outputs.png)

紅框為量測區，編號22–24、28–30、34–36是原稿固定的同九顆柱子。瀏覽器的局部圖沿用各影格原本的追蹤窗口，窗口會隨影格移動，不能僅靠局部圖的相對位置估算位移；完整圖與實際圓心座標才保留影像座標位置。另附的首對比較特別使用前後相同畫面座標，方便看出移動。

## 四組資料

| 倍率 | 設定步距 μm | 採集日期 | 原序列張數 | 這次用到的不同影像 | 原鎖定配對 | 每像素代表 μm |
|---|---:|---|---:|---:|---:|---:|
| 50× | 0.5 | 2026-07-02 | 51 | 44 | 30 | 0.0690 |
| 50× | 1.0 | 2026-07-02 | 50 | 42 | 30 | 0.0690 |
| 20× | 0.5 | 2026-07-04 | 50 | 39 | 30 | 0.1725 |
| 20× | 1.0 | 2026-07-04 | 50 | 41 | 30 | 0.1725 |

全部實際輸入為2048×1536、8位元灰階BMP；數字除255轉到0–1後處理，沒有放大影像或重排像素。本次量測入口直接讀取這些原稿的量測輸入；不額外旋轉或翻轉。設定中20×的拍攝方向標註不等於本次又翻轉影像。

原序列共有201張，本次120組配對共用166張不同影像。每對前後編號相差1，但不是只取前31張，也不是120次獨立重拍。

## 為何是這120組

沿用投稿前由Raw訂好的名單：先採用原25%可用性門檻且不跨拍攝分段的相鄰配對，再依Raw與名義步距的差、九顆差異、影格順序排序，取各組30對。這次不重新選圖、不以R152表現決定納入或排除。這是既定選樣下的公平方法比較，不是未篩選完整錄影的效能。

## 三方法怎麼處理同一張圖

| 項目 | Raw | Fixed Wiener | R152 |
|---|---|---|---|
| 輸入 | 同一原始量測影像 | 同一影像的原九顆窗口 | 同一張完整影像 |
| 光學資料 | 不使用 | 各倍率原校正單核，101×101 | 20×原生25顆101×101；50×原校正1顆101×101 |
| 固定設定 | 原灰階 | 正規量0.0565，沿用原背景／對比處理 | 同一已交付權重，交付倍率1，不重訓 |
| 額外影像修改 | 無 | 僅原Wiener處理 | 無後續銳化、移位、尺寸修正或量化 |
| 後續量測 | 相同原稿程式 | 相同原稿程式 | 相同原稿程式 |

Wiener的細節：背景估計範圍半徑20×為10像素、50×為26像素；對比使用99.5百分位正規化；反濾波周邊各補50像素，使用原對稱邊界延伸。這些是原稿的Wiener方法，不是重新調出的設定。

R152的50×輸入只是暫時接入原單顆校正：兩處光學計算都切換到50×核，權重固定1。原25顆選擇器的已學參數保留，沒有假造25顆50×資料。拿掉外部單核即可還原原生用法，已測得還原輸出逐像素相同。

## 找邊界與圓心的實際設定

先找粗略外框，再沿外框垂直方向尋找亮度變化最強的位置，最後用這些位置找圓心。不是拿神經網路直接預測的移動量當答案。

| 設定 | 20× | 50× |
|---|---:|---:|
| 預估柱子半徑，像素 | 7.6 | 19.5 |
| 柱子中心間距，像素 | 29.0 | 72.5 |
| 九顆整體窗口外加邊界，像素 | 16 | 40 |
| 每顆取圖半寬，像素 | 14（通常29×29） | 34（通常69×69） |
| 每顆外框取樣點數 | 64 | 96 |
| 粗外框更新次數 | 13 | 15 |
| 沿外框垂直方向搜尋半寬，像素 | 2.4 | 4.0 |
| 搜尋取樣間距，像素 | 0.10 | 0.10 |
| 亮度曲線平滑寬度，像素 | 0.65 | 0.65 |
| 柱子亮暗方向 | 暗柱、較亮背景 | 暗柱、較亮背景 |

峰值位置使用鄰近三點作細化；圓心由邊界點到圓的距離差最小化取得。原設定另有搜尋半徑4／8像素、最少7顆等上游可用性欄位，不等於本輪量測器又重新用它們篩掉結果。本次保留九顆並完整量測每一個鎖定配對。

設定步距用來預估柱子搜尋位置，也用在最後算與名義步距的差；它不作為圓擬合的答案。50×拍攝中有原本的分段位置重設，沿用原分段錨點，沒有把跨段影格當普通相鄰步距。

## R152運算設定

| 項目 | 本次固定值與意義 |
|---|---|
| 已完成訓練的交付點 | 第8192次保存點，交付倍率1 |
| 計算精度 | 32位元浮點；未使用較低精度加速 |
| 執行顯示卡 | NVIDIA RTX A6000 |
| 原尺寸分塊 | 每塊保留512×512，另讀周邊24像素；脈絡及光學運算仍使用完整影像 |
| R152光學反濾波正規量 | 0.03；與Wiener的0.0565是不同方法的各自固定設定 |
| 反向增益上限 | 2.0 |
| 作用頻率範圍 | 最高可表達頻率的0.25倍以内，即0.125週期／像素以内 |
| 光學單次修正限制 | ±0.25（影像亮度已轉成0–1） |
| 已學好的內部比例 | 約0.0119699 |
| 已學好的外部安全比例 | 約0.0138008 |

所有比例保持交付值；不因哪一張或哪個倍率的量測分數更好而調整。50×原校正略不對稱，本次保留原位置和形狀，沒有另做中心平移或強制對稱。

## 三個結果怎麼算

1. 一對影像：各自找九顆圓心，算九個有正負方向的水平位移；九個位移的中位數再取絕對值，代表這一步的步距。
2. 步距波動：每條件30步的樣本標準差，再將四條件平均。
3. 與設定步距的平均差：每一步和0.5或1.0 μm設定值相減取絕對值，每條件平均後再平均四條件。
4. 九顆之間的差異：每對影像九個有號水平位移的樣本標準差，再取120對的中位數。

結果使用名義步距，不是平台逐張回授真值，也不是二維移動長度。所有標準差使用樣本讀法；三項不合成可調總分。原稿的配對區間方法另以每條件內配對重抽樣20000次、固定種子20260824計算；部分配對共用影像，不能當成獨立重拍證據。

## 尚未從本次鎖定來源確認的拍攝設定

曝光時間、照明強度、相機增益及每個物鏡的數值孔徑，沒有在本次配對／模型／量測設定中得到逐序列可核對紀錄，因此這裡不補推測值。若要把本頁擴成完整儀器採集方法，還需對照原拍攝日誌。

## 可追溯資料

- [120組原配對與拍攝時間](../sources/original_locked_pairs.csv)
- [166張實際原圖位置及核對值](../results/raw_frame_manifest.csv)
- [全部配對三方法讀值](../results/full120/per_pair.csv)
- [九顆逐張圓心](../results/full120/centers.csv)
- [來源、接線與協議報告](../reports/R152_AUDIT.md)
'''
    (OUT/'EXPERIMENT_DESIGN.md').write_text(design,encoding='utf-8')
    (OUT/'build_check.json').write_text(json.dumps(dict(source_frames_verified=166,output_frames_verified=166,pairs=120,conditions=4,display_range=[0,1],display_crops='original per-frame measurement windows',full_preview='downsampled only for display; original input shape 2048x1536'),indent=2)+'\n')
    print('Inspection evidence ready',OUT)
if __name__=='__main__':main()
