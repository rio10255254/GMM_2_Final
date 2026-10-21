"""Show predeclared fixed-pillar examples and the sole adverse observation."""
from pathlib import Path
import json
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
data=loadmat(OUT/'measured_arrays.mat',variable_names=['cells','masks','truth_masks'])
examples=[(13,21,'Fixed pillar / exposure 13'),(20,21,'Fixed pillar / exposure 20'),
          (24,21,'Fixed pillar / exposure 24'),(22,6,'Only contour regression vs full')]
names=['Raw','Full E42','Position off','Reduced full correction']
fig,axes=plt.subplots(4,4,figsize=(11,11),layout='constrained')
for r,(exp,pillar,label) in enumerate(examples):
    raw=data['cells'][:,:,pillar-1,exp-13,0]
    lo,hi=np.percentile(raw,[1,99])
    for m in range(4):
        ax=axes[r,m];im=data['cells'][:,:,pillar-1,exp-13,m]
        ax.imshow(im,cmap='gray',vmin=lo,vmax=hi,interpolation='nearest')
        if r==3:
            ax.contour(data['truth_masks'][:,:,pillar-1],levels=[.5],colors=['#EFCA6E'],linewidths=.8)
            ax.contour(data['masks'][:,:,pillar-1,exp-13,m],levels=[.5],colors=['#78B2D4'],linewidths=.8)
        ax.set_xticks([]);ax.set_yticks([])
        if r==0:ax.set_title(names[m],fontsize=12)
        if m==0:ax.set_ylabel(f'Exposure {exp}, pillar {pillar}',fontsize=10)
fig.suptitle('Frozen E42 outputs and the retained exception\nSame display limits per row; last row: yellow SEM, cyan measured contour (unaligned)',fontsize=14)
fig.savefig(OUT/'review_examples.png',dpi=170)
plt.close(fig)
with (OUT/'visual_selection.json').open('x',encoding='utf-8') as f:
    json.dump({'examples':examples,'selection':'Pillar 21 is fixed; exposure 22 pillar 6 is the sole worse boundary observation and included intentionally, not excluded.'},f,indent=2)
