"""Show verified real optical photographs and the one retained model's outputs."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def main():
    out=ROOT/'results/pillar_visual_review';out.mkdir(parents=True,exist_ok=False)
    figures=ROOT/'reports/figures';panel=load(R125/'results/real_panel_v2/frozen_panel.json')
    selected=ROOT/'runs/P_s1285002/evaluations/real_step8192'
    original_verification=load(selected/'verification.json')
    checkpoint=load(ROOT/'trial/manifest.json')['checkpoint'];assert sha(checkpoint['path'])==checkpoint['sha256']
    source=next(x['source'] for x in panel['full_images'] if x['name']=='sem_optical_exposure13')
    assert sha(source['path'])==source['sha256']
    path=selected/'full_images/sem_optical_exposure13/output_float.npz'
    assert sha(path)==original_verification['output_sha256'][str(path)]
    raw=cv2.imread(source['path'],0).astype(np.float32)/np.float32(255)
    with np.load(path) as f:prediction=f['output']
    assert raw.shape==prediction.shape==(821,821)
    with np.load(R127/'results/sem_native_v2/native_references.npz') as f:centers=f['optical_centers'].reshape(6,6,2)
    center=centers[2,2];cx,cy=np.rint(center).astype(int);half=64;box=[int(cx-half),int(cy-half),int(cx+half),int(cy+half)]
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei'
    def pair(a,b,title,caption,name,figsize):
        fig,axes=plt.subplots(1,2,figsize=figsize)
        for ax,img,label in zip(axes,[a,b],['原始實拍照片','目前模型重建']):
            ax.imshow(img,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(label,fontsize=15,pad=10);ax.set_xticks([]);ax.set_yticks([])
        fig.suptitle(title,fontsize=19,y=.98)
        fig.text(.5,.025,caption,ha='center',fontsize=11,color='#333333')
        fig.tight_layout(rect=[0,.055,1,.93]);fig.savefig(figures/name,dpi=160);plt.close(fig)
    pair(raw,prediction,'真實 pillar 影像：同一張照片的前後比較','一般亮度、完整36個柱體；左右皆使用相同的0–255灰階顯示範圍。','selected_pillar_full.png',(12,6.8))
    x0,y0,x1,y1=box
    pair(raw[y0:y1,x0:x1],prediction[y0:y1,x0:x1],'同一個 pillar 的局部放大','固定取第3列、第3行附近的同一區域；僅放大顯示，不改變原圖或模型輸出。','selected_pillar_zoom.png',(10,5.6))
    # Additional actual acquisition, with full-frame inference and fixed crop.
    item=next(x for x in panel['motion_pairs'] if x['sequence']=='50x_0p5um');source2=item['sources'][0];assert sha(source2['path'])==source2['sha256']
    path2=selected/'motion/50x_0p5um/frame0/output_float.npz';assert sha(path2)==original_verification['output_sha256'][str(path2)]
    raw2=cv2.imread(source2['path'],0).astype(np.float32)/np.float32(255)
    with np.load(path2) as f:pred2=f['output']
    box2=[1240,220,1580,560];x0,y0,x1,y1=box2
    pair(raw2[y0:y1,x0:x1],pred2[y0:y1,x0:x1],'另一組實拍資料中的 pillar 區域','取自完整位移影像的固定區域；左右相同位置與灰階範圍，並非另一組獨立SEM真值。','selected_pillar_second_acquisition.png',(10,5.8))
    for name,img in [('pillar_original.png',raw),('pillar_reconstruction.png',prediction)]:
        assert cv2.imwrite(str(out/name),np.rint(img*255).clip(0,255).astype(np.uint8))
    save(out/'manifest.json',dict(created_utc=now(),checkpoint=checkpoint,primary_source=source,primary_model_output=record(path),primary_shape=list(raw.shape),primary_zoom_box=box,primary_magnification='unverified; not inferred from directory name',secondary_source=source2,secondary_model_output=record(path2),secondary_crop_box=box2,display_range_gray=[0,255],same_display_scale_and_coordinates=True,source_and_model_pixels_not_edited=True,figures=[record(figures/name) for name in ['selected_pillar_full.png','selected_pillar_zoom.png','selected_pillar_second_acquisition.png']],original_source_still_unchanged=sha(source['path'])==source['sha256'],model_kind='single retained P_s1285002 final8192',production_measurement_qualified=False,source_script=record(__file__)))
    print(json.dumps(dict(primary_source=source['path'],selected_model=checkpoint['path'],figures=3)),flush=True)

if __name__=='__main__':main()
