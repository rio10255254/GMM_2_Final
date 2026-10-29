import cv2,pandas as pd
from scipy.io import loadmat
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from common import *
from compare_native_sizes import crossing_radii
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei';plt.rcParams['axes.unicode_minus']=False
    root=ROOT/'results/sem_native_v2';d=np.load(root/'native_references.npz');objects=pd.read_csv(root/'native_SEM_objects.csv');row=objects[(objects.file==1)&(objects.local==1)].iloc[0];pid=int(row.pillar)
    sem=np.array(Image.open(str(PROJECT_ROOT / 'Shared_Sources/SEM_Originals/P-01.tiff')))[...,0];opt=cv2.imread(str(EXPS/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/13.bmp'),0);mapping=loadmat(EXPS/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['global_index'])['global_index'];gy,gx=np.argwhere(mapping==pid)[0];oc=d['optical_centers'][gy*6+gx];sc=np.array([row.center_x,row.center_y]);theta=np.arange(720)*2*np.pi/720;co,si=np.cos(theta),np.sin(theta)
    fig,axes=plt.subplots(1,2,figsize=(11,5.5))
    axes[0].imshow(sem,cmap='gray',vmin=0,vmax=255)
    for name,color,label in [('inner','#49b594','亮帶內側'),('rim','#eab54f','亮帶中心'),('outer','#db6c5d','亮帶外側')]:
        radius=d[f'p{pid:02d}_{name}'];axes[0].plot(sc[0]+co*radius,sc[1]+si*radius,c=color,lw=1,label=label)
    axes[0].set(xlim=(sc[0]-135,sc[0]+135),ylim=(sc[1]+135,sc[1]-135));axes[0].set_title('原始SEM：亮邊有厚度\n三種位置代表不同的取邊定義');axes[0].legend(fontsize=9)
    axes[1].imshow(opt,cmap='gray',vmin=0,vmax=255);radius,valid,_=crossing_radii(opt.astype(float)/255,[oc]);radius=radius[0];radius[~valid[0]]=np.nan;axes[1].plot(oc[0]+co*radius,oc[1]+si*radius,c='#59b0e4',lw=1.5,label='光學亮暗過渡中點')
    axes[1].set(xlim=(oc[0]-48,oc[0]+48),ylim=(oc[1]+48,oc[1]-48));axes[1].set_title('同一顆柱子的光學照片\n量到的亮暗位置，仍須確認物理意義');axes[1].legend(fontsize=9)
    for ax in axes:ax.set_aspect('equal');ax.axis('off')
    fig.suptitle('新對照保留SEM原始像素，先比較尺寸相對柱距的比例\n圖中的位置範圍是取邊方式的差異，不是已校準的物理誤差範圍',fontsize=13)
    fig.tight_layout();out=ROOT/'reports/figures';out.mkdir(exist_ok=True);fig.savefig(out/'native_SEM_edge_definitions.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
