from pathlib import Path
import json,cv2,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';O=B/'direction_evidence'
plan=json.loads((R/'config/plan.json').read_text(encoding='utf-8-sig'));im=cv2.imread(plan['frames'][0]['source']['path'],0)
cfg=json.loads((R/'config/sem_corner9_lsc_plan.json').read_text());centers=np.array(cfg['base_centers']);measure=[]
def brightness(c,kind):
 x,y=np.rint(c).astype(int);patch=im[y-13:y+14,x-13:x+14].astype(float);yy,xx=np.indices(patch.shape);rr=np.hypot(xx-13,yy-13);inside=float(np.mean(patch[rr<=4]));outside=float(np.mean(patch[(rr>=11)&(rr<=13)]));return dict(kind=kind,x=x,y=y,inside=inside,outside=outside,inside_minus_outside=inside-outside)
for c in centers:measure.append(brightness(c,'pillar'))
roi=im[825:1020,1680:1890];_,mask=cv2.threshold(roi,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU);_,_,st,cs=cv2.connectedComponentsWithStats(mask);use=(st[:,4]>100)&(st[:,4]<500)&(cs[:,0]>14)&(cs[:,0]<196)&(cs[:,1]>14)&(cs[:,1]<181)
for c in cs[use]+[1680,825]:measure.append(brightness(c,'via'))
df=pd.DataFrame(measure);df.to_csv(O/'polarity_measurements.csv',index=False);g=df.groupby('kind')[['inside','outside','inside_minus_outside']].median();assert g.loc['pillar','inside_minus_outside']<0 and g.loc['via','inside_minus_outside']>0
fig,axs=plt.subplots(1,3,figsize=(12,4))
for ax,name,title in zip(axs,['mirror_common.png','current_common.png','rotate90_common.png'],['Historical: horizontal mirror','September raw image','Historical: 90-degree rotation']):
 ax.imshow(cv2.imread(str(O/name),0),cmap='gray',vmin=0,vmax=255);ax.set_title(title,fontsize=10);ax.axis('off')
fig.suptitle('Polarity agrees in both candidates; common cross pattern is nearly symmetric',fontsize=11);fig.tight_layout();fig.savefig(O/'polarity_direction_evidence.png',dpi=180)
mapping=[22,23,24,28,29,30,34,35,36];table=pd.DataFrame({'new_local_id':range(1,10),'row_from_top':np.repeat([1,2,3],3),'column_from_left':np.tile([1,2,3],3),'SEM_ID_inferred':mapping,'status':'inferred_horizontal_mirror_not_uniquely_proven'})
table.to_csv(O/'working_sem_mapping.csv',index=False)
result={'working_orientation':'horizontal_mirror','status':'inferred_not_unique_identification','reason':'Correct pillar/via polarity plus higher whole-frame match; not selected using reconstructed contour error or model ranking','whole_frame_correlation':{'horizontal_mirror':.962689220905304,'rotate90':.9364241361618042},'same_region_refined_correlation':{'horizontal_mirror':.9789508737919403,'rotate90':.9786806773332064},'limitation':'Pillar upper-left / via lower-right and line quadrants occur for both candidates; polarity alone does not distinguish them. Same-region result almost tied.','working_sem_ids':mapping,'alternative_sem_ids':[22,28,34,23,29,35,24,30,36],'group_size_and_repeatability':'unchanged','model_metrics_used_for_orientation':False,'polarity_median':g.to_dict(orient='index')}
(O/'direction_decision.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
report='''# SEM方向的明暗核對與工作推定

2026-09-19。按照使用者要求，補查原圖的柱、孔及十字區明暗。

九月左上為亮底暗柱，右下為暗底亮孔。原始SEM對位程式也將柱P影像對到暗柱光學區、孔V影像對到亮孔光學區；分類沒有反用。數值見polarity_measurements.csv。

整視野對位相關：左右鏡像0.962689，90度旋轉0.936424，較支持左右鏡像。因此選擇**左右鏡像作工作推定**，而不是繼續將兩者當無優先順序的版本。沒有用任何模型的尺寸或輪廓成績來選方向。

但兩種變換都保留「左上暗柱／右下亮孔」和橫直線象限配置。為排除兩種候選比較區域大小不同的影響，又在相同原圖矩形x1450:1840、y600:1000，允許很小的對位修正後比較，得到0.978951與0.978681，幾乎相同。因此明暗足以確認P/V，無法單獨唯一排除90度轉向；工作推定不冒充歷史紀錄或獨特特徵已認證。

目前採用的九顆排列（由上到下、由左到右）：

```
22 23 24
28 29 30
34 35 36
```

原候選1即此排列。候選2作方向敏感度保留。九顆平均尺寸、位移及重拍統計不變；逐顆輪廓結論仍註明推定方向。後續若找到拍攝轉向紀錄或跨年代一致的不對稱特徵，再提升為唯一已確認方向。

原始影像：H:/From_2TB_D_disk/13_thesis/SEM_data。當年排序紀錄：其下ordering_result_20260729。歷史6×6編號已由via_pilar.xlsx的SEM data!J5:O10與SEM2img_v2.m逐項核對，並無未確定的歷史SEM排序。

圖：results/sem_corner9/direction_evidence/polarity_direction_evidence.png；推定對照：working_sem_mapping.csv；核對依據：direction_decision.json。
'''
(R/'reports/R136_SEM_DIRECTION_RESULTS.md').write_text(report,encoding='utf-8')
with (R/'HANDOFF.md').open('a',encoding='utf-8') as f:f.write('\n## Brightness direction followup2026-09-19\nHistorical SEM order verified. P/V polarity checked in raw. Working inference horizontal mirror -> [[22,23,24],[28,29,30],[34,35,36]], not uniquely proven: common region correlations0.978951vs0.978681. See reports/R136_SEM_DIRECTION_RESULTS.md and results/sem_corner9/direction_evidence. Never silently relabel as verified. Metrics/model score not used to select orientation.\n')
print(g.to_string());print('Working mapping recorded as inference, not unique proof.')
