"""Actual PSF matrices, paired native images and all 30 measured contours."""
from __future__ import annotations
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LogNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from scipy.io import loadmat
import torch
from pypdf import PdfWriter

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
DOC=ROOT/'reports/R152_THESIS_VISUAL_EVIDENCE_20261003'
FIG=DOC/'figures';DATA=DOC/'data';CAL=DOC/'calibration'
PX_UM=.1725
MAIN_RUN_INDEX=16;FRAME_INDEX=0;PILLAR_ID=5
ANGLE=np.linspace(0,2*np.pi,720,endpoint=False)
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
                     'font.size':10,'axes.labelsize':10,'axes.linewidth':.7,
                     'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'
def save(fig,name,dpi=450):
    for ext in ('png','pdf','svg'):fig.savefig(FIG/f'{name}.{ext}',dpi=dpi)
    plt.close(fig)
def profiles(points,centers):
    results=[]
    for p,c in zip(points,centers):
        q=p-c;a=np.mod(np.arctan2(q[:,1],q[:,0]),2*np.pi);r=np.linalg.norm(q,axis=1)
        order=np.argsort(a);a,r=a[order],r[order]
        results.append(np.interp(ANGLE,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]]))
    return np.array(results)*PX_UM*1000
def fwhm(line):
    x=np.arange(-50,51,dtype=float);target=float(line[50]/2)
    pos=np.flatnonzero(line[50:]<=target)[0]+50
    crossing=np.interp(target,[line[pos],line[pos-1]],[x[pos],x[pos-1]])
    return 2*float(crossing)

def main():
    for p in (OUT,DOC,FIG,DATA,CAL):p.mkdir(parents=True,exist_ok=True)
    lock=read(ROOT/'calibration/BANK_LOCK.json')
    bank_path=ROOT/'calibration/measured_psf_bank.npz';mat_path=Path(lock['source_mat_path'])
    assert sha(bank_path)==lock['bank_sha256'] and sha(mat_path)==lock['source_mat_sha256']
    with np.load(bank_path,allow_pickle=False) as z:bank=z['all_kernels'].copy()
    mat=loadmat(mat_path);ordered=np.stack([mat['psf_grid'][:,:,r,c] for r in range(5) for c in range(5)])
    assert bank.shape==(25,101,101) and np.array_equal(bank,ordered)
    assert np.isfinite(bank).all() and (bank>=0).all() and np.max(np.abs(bank.sum((1,2))-1))<1e-12
    names=[str(mat['source_image_names_row_major'][r,c].item()) for r in range(5) for c in range(5)]
    assert names==lock['source_image_names_row_major'] and abs(float(mat['object_pixel_um'].item())-PX_UM)<1e-15
    complete=read(ROOT/'runs/formal_8192/training_complete.json');cp_path=Path(complete['deployed_checkpoint']['path'])
    assert sha(cp_path)==complete['deployed_checkpoint']['sha256']
    cp=torch.load(cp_path,map_location='cpu',weights_only=False)
    actual_bank=cp['model']['psf_fusion.bank'][:,0].numpy()
    assert np.array_equal(actual_bank,(bank/bank.sum((1,2),keepdims=True)).astype(np.float32))
    assert np.array_equal(cp['model']['base.optics.bank'][:,0].numpy(),actual_bank)
    np.savez_compressed(DATA/'actual_deployed_PSF25_float32.npz',kernels=actual_bank)
    shutil.copy2(bank_path,CAL/'measured_psf_bank.npz');shutil.copy2(mat_path,CAL/mat_path.name)
    shutil.copy2(ROOT/'calibration/BANK_LOCK.json',CAL/'BANK_LOCK.json')
    source_index=[]
    calibration_dir=mat_path.parent
    for name in ('full25_core_halo_qa.csv','full25_core_halo_summary.json','E_full_patch_metrics.csv',
                 'E_full_patch_per_pillar.csv','E_full_patch_verdict.json','full_patch_folds.json',
                 'selected_full_patch_before_E.json','README_TW.md','source_sha256.csv'):
        source=calibration_dir/name;assert source.is_file();shutil.copy2(source,CAL/name)
        source_index.append(dict(role='PSF_calibration',source=str(source),sha256=sha(source),copy='calibration/'+name))
    qa=pd.read_csv(calibration_dir/'full25_core_halo_qa.csv')
    assert len(qa)==25 and qa.source_image.tolist()==names
    yy,xx=np.mgrid[-50:51,-50:51];rad=np.hypot(xx,yy)
    psf_rows=[]
    for k,kernel in enumerate(bank):
        q=qa.iloc[k]
        assert abs(q.sigma_core_px-mat['sigma_core_px'][k//5,k%5])<1e-12
        assert abs(q.sigma_halo_px-mat['sigma_halo_px'][k//5,k%5])<1e-12
        assert abs(q.core_energy_weight-mat['core_energy_weight'][k//5,k%5])<1e-12
        core=np.exp(-(xx*xx+yy*yy)/(2*q.sigma_core_px**2));core/=core.sum()
        halo=np.exp(-(xx*xx+yy*yy)/(2*q.sigma_halo_px**2));halo/=halo.sum()
        reproduced=q.core_energy_weight*core+(1-q.core_energy_weight)*halo
        assert np.max(np.abs(reproduced-kernel))<1e-12
        np.savetxt(DATA/f'PSF_{k+1:02d}_101x101.csv',kernel,delimiter=',',fmt='%.17e')
        assert np.array_equal(np.loadtxt(DATA/f'PSF_{k+1:02d}_101x101.csv',delimiter=','),kernel)
        psf_rows.append(dict(psf_number=k+1,model_index=k,grid_row=k//5+1,grid_col=k%5+1,
                             source_image=names[k],sigma_core_px=q.sigma_core_px,sigma_core_um=q.sigma_core_px*PX_UM,
                             sigma_halo_px=q.sigma_halo_px,sigma_halo_um=q.sigma_halo_px*PX_UM,
                             core_energy_weight=q.core_energy_weight,brightness_gain=q.brightness_gain,
                             peak=float(kernel.max()),kernel_sum=float(kernel.sum()),
                             centroid_x_px=float((kernel*xx).sum()),centroid_y_px=float((kernel*yy).sum()),
                             fwhm_x_um=fwhm(kernel[50])*PX_UM,
                             crop41_energy_fraction=float(kernel[30:71,30:71].sum()),
                             energy_outside_radius15_fraction=float(kernel[rad>=15].sum()),
                             fit_loss=q.fit_loss,fit_exitflag=int(q.fit_exitflag)))
    psf_data=pd.DataFrame(psf_rows);psf_data.to_csv(DATA/'PSF25_calibration_and_matrix_metrics.csv',index=False,encoding='utf-8-sig')
    peak=float(bank.max())
    for half,log,name in [(20,False,'Fig6_3_PSF25_actual_response'),(50,True,'Appendix_PSF25_full101_log_response')]:
        fig,axs=plt.subplots(5,5,figsize=(8.2,8.5))
        fig.subplots_adjust(left=.065,right=.87,bottom=.055,top=.92,wspace=.22,hspace=.43)
        fig.suptitle('25 PSFs used by R152: '+('full 101 x 101, logarithmic display' if log else 'actual response, common linear display'),y=.985,fontsize=12)
        norm=LogNorm(vmin=1e-6,vmax=peak,clip=True) if log else Normalize(vmin=0,vmax=peak)
        cmap=plt.get_cmap('gray_r').copy();cmap.set_bad('white')
        extent=np.array([-half-.5,half+.5,-half-.5,half+.5])*PX_UM
        for k,ax in enumerate(axs.flat):
            part=bank[k,50-half:51+half,50-half:51+half]
            im=ax.imshow(part,cmap=cmap,norm=norm,origin='lower',interpolation='nearest',extent=extent)
            ax.set_title(f'PSF {k+1:02d}  {names[k]}' if log else f'PSF {k+1:02d}',fontsize=7.6 if log else 9.5,pad=3)
            ticks=[-8,0,8] if log else [-3,0,3]
            ax.set_xticks(ticks);ax.set_yticks(ticks);ax.tick_params(labelsize=7,length=2,pad=1)
            if k//5==4:ax.set_xlabel('x (µm)',fontsize=8,labelpad=1)
            if k%5==0:ax.set_ylabel('y (µm)',fontsize=8,labelpad=1)
        cax=fig.add_axes([.905,.19,.023,.58]);bar=fig.colorbar(im,cax=cax)
        bar.set_label('Normalized PSF weight per pixel',fontsize=9);bar.ax.tick_params(labelsize=8)
        if not log:bar.set_ticks([0,.01,.02,.03,.04])
        save(fig,name)
    plan=read(ROOT/'evaluation/capture_plan.json')
    frame=next(f for f in plan['frames'] if f['run_index']==MAIN_RUN_INDEX and f['index']==FRAME_INDEX)
    raw_path=Path(frame['source']['path'])
    assert sha(raw_path)==frame['source']['sha256']
    receipt_path=ROOT/'results/reconstruction'/frame['run']/f"{frame['index']+1:02d}.json"
    receipt=read(receipt_path);native_path=Path(receipt['output_path'])
    assert receipt['checkpoint_sha256']==complete['deployed_checkpoint']['sha256'] and sha(native_path)==receipt['output_sha256']
    raw_u8=cv2.imread(str(raw_path),cv2.IMREAD_UNCHANGED)
    with np.load(native_path,allow_pickle=False) as z:mosr=z['output'].copy()
    assert raw_u8.shape==mosr.shape==(1544,2064) and raw_u8.dtype==np.uint8 and mosr.dtype==np.float32
    assert np.isfinite(mosr).all() and 0<=mosr.min() and mosr.max()<=1
    raw=raw_u8.astype(np.float32)/255
    centres=pd.read_csv(ROOT/'evaluation/baseline_centers/Raw'/f"{frame['run']}.csv")
    c=centres[(centres['index']==FRAME_INDEX)&(centres.pillar_id==PILLAR_ID)].iloc[0]
    cx,cy=int(round(c.center_x_px)),int(round(c.center_y_px));half=64
    bounds=dict(x0=cx-half,x1=cx+half+1,y0=cy-half,y1=cy+half+1)
    roi=(slice(bounds['y0'],bounds['y1']),slice(bounds['x0'],bounds['x1']))
    assert raw[roi].shape==(129,129)
    np.savez_compressed(DATA/'same_region_native_crops.npz',RAW=raw[roi],R152=mosr[roi],
                        crop_bounds_xyxy=np.array([bounds['x0'],bounds['y0'],bounds['x1'],bounds['y1']]),object_um_per_px=PX_UM)
    shutil.copy2(raw_path,DATA/'RAW_same_frame_original.bmp')
    shutil.copy2(native_path,DATA/'R152_same_frame_original_float32.npz')
    cv2.imwrite(str(DATA/'RAW_same_frame_native_u8.png'),raw_u8)
    preview=np.rint(mosr.astype(np.float64)*65535).clip(0,65535).astype(np.uint16)
    cv2.imwrite(str(DATA/'R152_same_frame_display_u16.png'),preview)
    assert np.array_equal(cv2.imread(str(DATA/'RAW_same_frame_native_u8.png'),-1),raw_u8)
    assert np.max(np.abs(preview.astype(float)/65535-mosr))<.5001/65535
    fig,axs=plt.subplots(2,2,figsize=(7.2,7.0),gridspec_kw={'height_ratios':[1544/2064,1]})
    fig.subplots_adjust(left=.02,right=.98,bottom=.055,top=.95,wspace=.035,hspace=.13)
    def image(ax,array,title,scale):
        ax.imshow(array,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_axis_off();ax.set_title(title,fontsize=10,pad=5)
        h,w=array.shape;length=scale/PX_UM;x=.06*w;y=.91*h
        ax.plot([x,x+length],[y,y],color='white',linewidth=2.2)
        ax.text(x+length/2,y-.035*h,f'{scale:g} µm',ha='center',va='bottom',color='white',fontsize=8,
                bbox=dict(facecolor='black',edgecolor='none',alpha=.6,pad=1))
    for col,(label,array) in enumerate([('RAW',raw),('MOSR (R152)',mosr)]):
        image(axs[0,col],array,f'({chr(97+col)}) {label}: same field',50)
        axs[0,col].add_patch(Rectangle((bounds['x0']-.5,bounds['y0']-.5),129,129,fill=False,edgecolor='white',linewidth=.75))
        image(axs[1,col],array[roi],f'({chr(99+col)}) {label}: identical local region',5)
        local_x=float(c.center_x_px-bounds['x0']);local_y=float(c.center_y_px-bounds['y0'])
        axs[1,col].add_patch(Rectangle((local_x-13,local_y-13),26,26,fill=False,edgecolor='white',linewidth=.65))
        axs[1,col].text(local_x+14,local_y-14,'5',color='white',fontsize=8,ha='left',va='bottom',
                        bbox=dict(facecolor='black',edgecolor='none',alpha=.6,pad=.5))
    fig.text(.5,.012,'Scan 16, start frame; both sides use the same fixed linear display range [0, 1].',ha='center',fontsize=8.5)
    save(fig,'Sect6_2_3_RAW_MOSR_same_region')
    # All contours are saved measurements, not fitted circles or averaged synthetic curves.
    point_sets={};center_sets={};diameter_sets={};local_stats=[];contour_rows=[];measurement_sources=[]
    for method in ('RAW','R152'):
        directory=ROOT/'evaluation/baseline_centers/Raw' if method=='RAW' else ROOT/'results/centers'
        points=[];center=[];diameter=[]
        for run in plan['runs']:
            csv=directory/(run['run']+'.csv');npz=directory/(run['run']+'.npz')
            df=pd.read_csv(csv).sort_values(['index','pillar_id'])
            df=df[df['index']==FRAME_INDEX];assert len(df)==9 and df.pillar_id.tolist()==list(range(1,10))
            with np.load(npz,allow_pickle=False) as z:points.append(z['points'][FRAME_INDEX].copy())
            center.append(df[['center_x_px','center_y_px']].to_numpy());diameter.append(df.radius_px.to_numpy()*2*PX_UM*1000)
            measurement_sources += [dict(role=method+'_circle_readout',source=str(csv),sha256=sha(csv)),
                                    dict(role=method+'_measured_boundaries',source=str(npz),sha256=sha(npz))]
        point_sets[method]=np.array(points);center_sets[method]=np.array(center);diameter_sets[method]=np.array(diameter)
        assert point_sets[method].shape==(30,9,64,2)
        for pid in range(1,10):
            ps=point_sets[method][:,pid-1];cs=center_sets[method][:,pid-1];radial=profiles(ps,cs)
            local_stats.append(dict(method=method,frame_index=FRAME_INDEX,pillar_id=pid,scans=30,points_per_contour=64,
                                    mean_diameter_nm=float(diameter_sets[method][:,pid-1].mean()),
                                    diameter_repeat_sd_nm=float(diameter_sets[method][:,pid-1].std(ddof=1)),
                                    contour_repeat_sd_nm=float(np.sqrt(radial.var(axis=0,ddof=1).mean())),
                                    desized_shape_repeat_sd_nm=float(np.sqrt((radial-radial.mean(1,keepdims=True)).var(axis=0,ddof=1).mean()))))
            for ix,run in enumerate(plan['runs']):
                for j,p in enumerate(ps[ix]):
                    relative=(p-cs[ix])*PX_UM
                    contour_rows.append(dict(method=method,scan=run['run_index'],run=run['run'],frame_index=FRAME_INDEX,
                                              pillar_id=pid,point_index=j,x_px=float(p[0]),y_px=float(p[1]),
                                              LSC_center_x_px=float(cs[ix,0]),LSC_center_y_px=float(cs[ix,1]),
                                              relative_x_um=float(relative[0]),relative_y_um=float(relative[1])))
    pd.DataFrame(contour_rows).to_csv(DATA/'all9_start_position_30_contours.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(local_stats).to_csv(DATA/'all9_start_position_repeat_statistics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(measurement_sources).to_csv(DATA/'contour_measurement_source_checksums.csv',index=False,encoding='utf-8-sig')
    np.savez_compressed(DATA/'all9_start_position_measured_contours.npz',RAW_points_px=point_sets['RAW'],
                        R152_points_px=point_sets['R152'],RAW_centers_px=center_sets['RAW'],R152_centers_px=center_sets['R152'],
                        RAW_diameters_nm=diameter_sets['RAW'],R152_diameters_nm=diameter_sets['R152'],
                        run_ids=np.array([r['run'] for r in plan['runs']]))
    relative={m:(point_sets[m]-center_sets[m][:,:,None,:])*PX_UM for m in point_sets}
    extent=max(np.abs(a).max() for a in relative.values());limit=math.ceil((extent+.03)/.25)*.25
    nominal=read(ROOT/'evaluation/measurement_config.json')['radius_px']*PX_UM
    edge_bounds=(nominal-.3,nominal+.3,-.4,.4)
    def plot30(ax,array,method,whole=True):
        for contour in array:
            closed=np.vstack([contour,contour[0]])
            ax.plot(closed[:,0],closed[:,1],color='0.4' if method=='RAW' else '0.0',alpha=.6,linewidth=.55)
        ax.set_aspect('equal');ax.grid(color='0.92',linewidth=.4);ax.spines[['right','top']].set_visible(False)
        if whole:ax.set_xlim(-limit,limit);ax.set_ylim(limit,-limit)
        else:ax.set_xlim(edge_bounds[:2]);ax.set_ylim(edge_bounds[3],edge_bounds[2])
        ax.set_xlabel('Relative x (µm)');ax.set_ylabel('Relative y (µm)')
    fig,axs=plt.subplots(2,2,figsize=(7.4,7.0))
    fig.subplots_adjust(left=.11,right=.98,bottom=.09,top=.94,wspace=.3,hspace=.35)
    for col,method in enumerate(('RAW','R152')):
        selected=relative[method][:,PILLAR_ID-1]
        plot30(axs[0,col],selected,method);plot30(axs[1,col],selected,method,False)
        axs[0,col].set_title(f'({chr(97+col)}) {"RAW" if method=="RAW" else "MOSR (R152)"}: all 30 contours',fontsize=10)
        axs[1,col].set_title(f'({chr(99+col)}) Identical edge region',fontsize=10)
        axs[0,col].add_patch(Rectangle((edge_bounds[0],edge_bounds[2]),edge_bounds[1]-edge_bounds[0],edge_bounds[3]-edge_bounds[2],
                                       fill=False,edgecolor='black',linewidth=.7,linestyle='--'))
    fig.text(.5,.013,'Central object 5, start position: translation removed only; size and orientation preserved.',ha='center',fontsize=8)
    save(fig,'Sect6_2_4_30_measured_contours')
    fig,axs=plt.subplots(3,6,figsize=(12.0,7.5))
    fig.subplots_adjust(left=.045,right=.99,bottom=.07,top=.92,wspace=.23,hspace=.3)
    fig.suptitle('All nine fixed objects: 30 measured contours at the start position',fontsize=12,y=.98)
    for pid in range(1,10):
        row=(pid-1)//3;pair=(pid-1)%3
        for col,method in enumerate(('RAW','R152')):
            ax=axs[row,2*pair+col];plot30(ax,relative[method][:,pid-1],method)
            ax.set_title(f'Object {pid}: {method}',fontsize=8);ax.tick_params(labelsize=6,length=2,pad=1)
            ax.set_xticks([-1,0,1]);ax.set_yticks([-1,0,1]);ax.set_xlabel('x (µm)' if row==2 else '',fontsize=7)
            ax.set_ylabel('y (µm)' if pair==0 and col==0 else '',fontsize=7)
    save(fig,'Appendix_all9_30_measured_contours')
    order=['Fig6_3_PSF25_actual_response','Sect6_2_3_RAW_MOSR_same_region','Sect6_2_4_30_measured_contours',
           'Appendix_PSF25_full101_log_response','Appendix_all9_30_measured_contours']
    writer=PdfWriter()
    for name in order:writer.append(FIG/f'{name}.pdf')
    with (DOC/'THESIS_VISUAL_FIGURES.pdf').open('wb') as f:writer.write(f)
    writer.close()
    main_stats=[x for x in local_stats if x['pillar_id']==PILLAR_ID]
    identity=dict(date='2026-10-03',PSF_bank_sha256=lock['bank_sha256'],source_MAT_sha256=lock['source_mat_sha256'],
                  matrix_order_equal_to_source_MAT=True,deployed_float32_PSFs_match=True,
                  PSF_count=25,PSF_matrix_size=[101,101],PSF_source_names=names,
                  PSF_main_display_crop=[30,71,30,71],PSF_main_min_retained_energy=float(psf_data.crop41_energy_fraction.min()),
                  PSF_common_linear_vmin=0.0,PSF_common_linear_vmax=peak,PSF_log_vmin=1e-6,
                  image_frame=frame,RAW_source_sha256=sha(raw_path),R152_native_source_sha256=sha(native_path),
                  checkpoint_sha256=receipt['checkpoint_sha256'],image_selection='fixed middle numbered scan 16; start frame 0; no score-based selection',
                  image_display={'vmin':0.0,'vmax':1.0,'interpolation':'nearest','independent_normalization':False},
                  image_crop_bounds=bounds,contour_selection={'frame_index':0,'pillar_id':5,'scans':30,'points_per_contour':64},
                  contour_alignment='subtract the stored LSC center separately for each contour; no scaling or rotation',
                  contour_coordinates='image x right-positive, y downward-positive; um, common limits',
                  contour_common_axis_limit_um=limit,contour_edge_zoom_bounds_um=list(edge_bounds),
                  central_object_statistics=main_stats,all9_start_statistics=local_stats,figure_page_order=order)
    (DOC/'DATA_AND_SELECTION.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding='utf-8')
    source_index += [dict(role='PSF_bank_used',source=str(bank_path),sha256=sha(bank_path),copy='calibration/measured_psf_bank.npz'),
                     dict(role='PSF_source_MAT',source=str(mat_path),sha256=sha(mat_path),copy='calibration/'+mat_path.name),
                     dict(role='RAW_real_image',source=str(raw_path),sha256=sha(raw_path),copy='data/RAW_same_frame_original.bmp'),
                     dict(role='MOSR_R152_native_output',source=str(native_path),sha256=sha(native_path),copy='data/R152_same_frame_original_float32.npz'),
                     dict(role='R152_checkpoint',source=str(cp_path),sha256=sha(cp_path))]
    (DOC/'SOURCE_INDEX.json').write_text(json.dumps(source_index,ensure_ascii=False,indent=2),encoding='utf-8')
    # Provide explicit captions and definitions, so the graphic cannot be mistaken for a schematic.
    stats={x['method']:x for x in main_stats}
    notes=f'''# R152論文三項實際圖像補件

日期：2026-10-03。比較影像的MOSR就是R152交付權重。這裡補的是實際矩陣、原生重建影像和保存的測得邊界，不使用舊Wiener圖或示意輪廓代替。

## 1 第6.1節與圖6-3 實際25顆PSF形貌

![實際使用的25顆PSF](figures/Fig6_3_PSF25_actual_response.png)

主圖每一格來自R152實際銀行的101×101矩陣，展示中央41×41像素的真實值，不是重新畫出的高斯示意。25格共用同一線性灰階范围0～{peak:.9f}，沒有逐顆除以峰值重新拉對比。每顆核總和為1。中央視圖保留每顆至少{psf_data.crop41_energy_fraction.min()*100:.6f}%的原矩陣能量；完整101×101以共同對數尺度另附在第四頁。對數圖只是顯示方式，沒有修改矩陣。

源MAT的psf_grid形狀為101×101×5×5，逐行順序與模型25顆完全一致；浮點部署保存點中的25個核也與銀行正規化後轉成float32完全相等。圖上PSF01～25對應模型索引0～24，左至右、上至下；來源檔名見下表及完整矩陣附圖。像素比例0.1725 µm/px；主圖像素中心范围−3.45～+3.45 µm，完整矩陣像素中心范围−8.625～+8.625 µm。

**可直接使用的中文圖說：** 圖6-3 本研究MOSR（R152）實際使用之25組PSF響應。PSF由本次系統成像資料擬合，依封存5×5順序排列。各核為101×101、非負且總和正規化為1；主圖展示中央41×41像素，25格採共同線性灰階尺度與共同物體空間座標。完整支持範圍及對數顯示另見附錄。此圖呈現實際核矩陣，不是PSF編號位置示意。

**English caption:** Actual responses of the 25 PSFs used by MOSR (R152), arranged in the archived row-major 5 x 5 order. Each PSF is a nonnegative, unit-sum 101 x 101 fitted system kernel. The central 41 x 41 samples are displayed with a common linear intensity scale and common object-space coordinates (0.1725 µm per pixel). The complete support and a common logarithmic display are provided in the appendix. No per-kernel peak normalization is applied.

### 對應校正資料

calibration內保存原始MAT、實際模型銀行、來源鎖、25張逐顆BADS參數及品質表、校正分組與E組保留驗證結果。data內提供25個可直接讀取的101×101 CSV矩陣、部署用float32核及逐顆彙整表。擬合形狀是同心兩高斯的離散正規化混合：h = w*g(sigma_core) + (1-w)*g(sigma_halo)，三個形狀參數和另外的亮度倍率均保留。每顆矩陣已用這些參數獨立重新產生並核對。

sigma_core範圍{psf_data.sigma_core_px.min():.6f}～{psf_data.sigma_core_px.max():.6f} px；sigma_halo範圍{psf_data.sigma_halo_px.min():.6f}～{psf_data.sigma_halo_px.max():.6f} px；核心能量比例{psf_data.core_energy_weight.min():.6f}～{psf_data.core_energy_weight.max():.6f}。亮度倍率保存在校正表中，沒有乘進已正規化PSF的能量。

'''
    notes += table(['PSF','模型索引','來源照片','核心sigma px','尾部sigma px','核心比例','亮度倍率'],
                   [[x.psf_number,x.model_index,x.source_image,f'{x.sigma_core_px:.6f}',f'{x.sigma_halo_px:.6f}',f'{x.core_energy_weight:.6f}',f'{x.brightness_gain:.6f}'] for x in psf_data.itertuples()])
    notes += f'''
## 2 第6.2.3節後 同區域RAW與MOSR原生影像

![相同區域RAW與R152影像及局部放大](figures/Sect6_2_3_RAW_MOSR_same_region.png)

固定使用第16趟004246_XY_0的起點（影像1.bmp，index 0，2026-09-03 00:42:47.944609 +08:00），不是按重建分數挑出的最好影像。兩方法使用同一1544×2064原圖，MOSR讀取已核對的R152原生float32輸出，不重新推論、不套用額外銳化、平移、尺寸修正或獨立對比拉伸。兩邊均以固定0～1線性亮度、最近樣本顯示；原圖只除以255。

上排是同一完整視野，白框標示下排相同局部範圍。下排129×129像素，以RAW中央物件5的已保存圓心決定，兩方法裁切座標完全相同：x=[{bounds['x0']},{bounds['x1']})，y=[{bounds['y0']},{bounds['y1']})，零起算。下排小方框與數字5標出後續輪廓圖的物件，方框不是測得輪廓。完整視野比例尺50 µm、局部比例尺5 µm。白框、文字及比例尺是圖表註記，沒有寫回模型影像。

**可直接使用的中文圖說：** 同一實拍視野之RAW與MOSR（R152）原生重建影像對照。（a,b）相同完整視野；（c,d）白框區域之相同座標局部放大，小方框標示後續30次轮廓疊圖的固定物件5。兩方法採共同固定線性亮度範圍，不作個別對比調整或後置銳化。影像取自第16趟起點。完整視野與局部圖比例尺分別為50 µm及5 µm。

**English caption:** RAW and native MOSR (R152) reconstruction of the same acquired frame. Panels (a,b) show the identical full field of view, and panels (c,d) show an identical-coordinate enlargement of the boxed region. The small boxes mark the same fixed object 5 used in the contour overlay. Both methods use the same fixed linear display range; no independent contrast stretching or post-reconstruction sharpening is applied. The frame is the start position of scan 16. Scale bars are 50 µm in the full-field panels and 5 µm in the enlarged panels.

原始BMP及R152原生NPZ以原檔複製附在data中，檔案雜湊與原驗證收據一致。另附RAW八位元PNG及R152十六位元顯示PNG；後者只是顯示格式的量化，量測與本圖仍直接使用float32原生輸出。局部兩個float32陣列也附在same_region_native_crops.npz。

## 3 第6.2.4節 同一物件30次實際輪廓

![同一物件30條測得輪廓](figures/Sect6_2_4_30_measured_contours.png)

固定比較3×3物件中的中央物件5、起點index 0，保留第1～30趟全部輪廓。每條線連接該次保存的64個最大梯度邊界點，並閉合首尾；沒有以擬合圓、平均輪廓或720方向插值曲線代替。只減去每條輪廓自己的已保存LSC圓心以移除平移，沒有縮放半徑、旋轉或自由形狀配準。兩方法共用比例與座標范围；x向右為正、影像y向下為正。

上排展示整個物件，下排展示同一右側邊界區域。下排只是相同30條折線的局部座標放大，沒有另算新的形狀。中央物件不按改善幅度選取；附錄同時展示起點九顆物件各自的30條輪廓。

**可直接使用的中文圖說：** 同一固定物件於30次重複掃描起點的實測輪廓疊圖。（a）RAW與（b）MOSR（R152）各包含30條由64個測得邊界點構成的輪廓；（c,d）為相同右側邊界區域的局部放大。各輪廓僅以自身LSC圓心移除平移，保留實際尺寸與方向，兩方法採相同物體空間尺度。此圖顯示邊界重複性，不以位置對齊後的輪廓推定圓心位移準度。

**English caption:** Overlay of 30 measured contours of the same fixed object at the start position of the repeated scans. Each curve joins the 64 saved maximum-gradient boundary points for one measurement. Panels (a,b) show RAW and MOSR (R152), respectively; panels (c,d) show the same right-side boundary region at enlarged scale. Each contour is translated by its own saved LSC center only, without radius normalization, rotation or free-form registration. Identical object-space scales are used for both methods.

### 此物件、此位置的對應數值

以下數值只對中央物件5、起點成立；不把它代替全30趟×31位置×9顆的整體輪廓統計。疊圖用64個原始測點；下表的輪廓SD為與主報告一致的720方向半徑插值後，跨30趟求變異再合併。

'''
    notes += table(['方法','平均直徑nm','直徑重拍SD nm','輪廓重拍SD nm','去尺寸形狀SD nm'],
                   [[m,*[f'{stats[m][k]:.6f}' for k in ('mean_diameter_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','desized_shape_repeat_sd_nm')]] for m in ('RAW','R152')])
    notes += '''
## 4 附錄、來源及交付

![完整101矩陣的共同對數顯示](figures/Appendix_PSF25_full101_log_response.png)

![起點九顆物件的全部30次輪廓](figures/Appendix_all9_30_measured_contours.png)

THESIS_VISUAL_FIGURES.pdf共五頁：前三頁依第6.1、6.2.3、6.2.4節順序排列；第四頁為25顆完整101×101共同對數顯示，第五頁為九顆起點輪廓補充。figures內每張都有高解析PNG、單張PDF及可編輯SVG。

DATA_AND_SELECTION.json明確保存影像、裁切、顯示范围、PSF索引、輪廓選擇與對齊方式；SOURCE_INDEX.json保存來源檔案及雜湊。all9_start_position_30_contours.csv共34560列（2方法×30趟×9顆×64点），同时保存絕對影像座標及平移後的物體空間座標；NPZ保留原始點與圓心。calibration提供原MAT、實際銀行及對應校正紀錄，data提供25個完整矩陣CSV。

這些圖補足實際形貌與影像證據，與完整統計報告一起使用。影像示例不代替全部930張的性能驗證；起點單一物件疊圖不代替全部位置的輪廓結果。PSF圖是實際使用的擬合系統核，沒有因模型成效重新更換核。
'''
    notes=notes.replace('范围','範圍').replace('64点','64點').replace('同时','同時').replace('轮廓','輪廓')
    (DOC/'FIGURE_NOTES.md').write_text(notes,encoding='utf-8')
    shutil.copy2(Path(__file__),DOC/'build_visual_evidence.py')
    print(json.dumps({'status':'built','PSF_count':25,'source_MAT_arrays_exact':True,
                      'checkpoint_bank_exact':True,'image_frame':frame['run']+'/1.bmp',
                      'main_contour_statistics':main_stats,'report':str(DOC/'FIGURE_NOTES.md'),
                      'PDFs':len(list(FIG.glob('*.pdf')))+1},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
