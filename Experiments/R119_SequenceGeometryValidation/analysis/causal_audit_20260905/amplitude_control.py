from pathlib import Path
import json
import cv2
import numpy as np

root=Path(__file__).resolve().parent/'sem_paths'
raw=cv2.imread(str(root/'Raw.png'),0).astype(float)
base=cv2.imread(str(root/'base.png'),0).astype(float)
no_shift=cv2.imread(str(root/'no_shift.png'),0).astype(float)
amount=lambda a:float(np.abs(a-raw).mean())
alpha=amount(no_shift)/amount(base)
control=np.rint(np.clip(raw+alpha*(base-raw),0,255)).astype(np.uint8)
path=root/'attenuation.png'
if path.exists():raise FileExistsError(path)
cv2.imwrite(str(path),control)
info={'global_alpha':alpha,'base_change_gray':amount(base),'no_shift_change_gray':amount(no_shift),
      'attenuation_change_gray':amount(control),'scope':'same frozen E42 on exposure 13; mechanical control only'}
(root/'amplitude_control.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info,indent=2))
