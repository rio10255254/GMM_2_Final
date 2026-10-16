"""Held-out image test: infer four known blur regimes from actual image texture."""
from __future__ import annotations
import json,sys,tempfile
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from optical.adaptive_psf import AdaptivePSFCue

REGIMES=((.65,.65),(3.0,3.0),(3.0,.65),(.65,3.0))

def create_scene(seed):
    rng=np.random.default_rng(seed)
    img=np.zeros((64,64),dtype=np.float32)
    for _ in range(14):
        x,y=rng.integers(4,60,size=2)
        if rng.random()<.5:
            cv2.circle(img,(int(x),int(y)),int(rng.integers(1,4)),1.0,-1)
        else:
            dx,dy=rng.integers(-9,10,size=2)
            cv2.line(img,(int(x),int(y)),(int(np.clip(x+dx,0,63)),int(np.clip(y+dy,0,63))),1.0,int(rng.integers(1,3)))
    return img

def features(image):
    dx=cv2.Sobel(image,cv2.CV_32F,1,0,ksize=3)
    dy=cv2.Sobel(image,cv2.CV_32F,0,1,ksize=3)
    lap=cv2.Laplacian(image,cv2.CV_32F,ksize=3)
    return np.stack([image,dx,dy,lap],axis=0)

def make_dataset(seeds,n):
    ids=[0,n//3,2*n//3,n-1]
    items=[];labels=[]
    for seed in seeds:
        clean=create_scene(seed)
        for class_id,(sx,sy) in enumerate(REGIMES):
            blurred=cv2.GaussianBlur(clean,(0,0),sigmaX=sx,sigmaY=sy,borderType=cv2.BORDER_REFLECT)
            items.append(features(blurred));labels.append(ids[class_id])
    return torch.from_numpy(np.stack(items)),torch.tensor(labels,dtype=torch.long),ids

def bank(path,n):
    y,x=np.mgrid[-50:51,-50:51]
    arr=[]
    for i in range(n):
        sx,sy=REGIMES[min(3,(i*4)//n)]
        v=np.exp(-.5*((x/sx)**2+(y/sy)**2));arr.append((v/v.sum()).astype('float32'))
    np.savez_compressed(path,all_kernels=np.stack(arr))

def run(n,k,temp):
    torch.manual_seed(888+n);torch.set_num_threads(2)
    path=temp/f'bank{n}.npz';bank(path,n)
    model=AdaptivePSFCue(4,path,n,k,regularization=.03)
    train_x,train_y,ids=make_dataset(range(64),n)
    test_x,test_y,_=make_dataset(range(1000,1016),n)
    optimizer=torch.optim.AdamW(model.selector.parameters(),lr=.01)
    generator=torch.Generator().manual_seed(2323+n)
    for step in range(301):
        ids_batch=torch.randint(0,len(train_x),(32,),generator=generator)
        optimizer.zero_grad(set_to_none=True)
        model.select(train_x[ids_batch])
        loss=model.selector_loss(train_y[ids_batch]);loss.backward();optimizer.step()
    with torch.no_grad():
        model.select(test_x)
        correct=(model.last_logits.argmax(1)==test_y)
        included=(model.last_indices==test_y[:,None]).any(1)
        by_class={str(label):float(correct[test_y==label].float().mean()) for label in ids}
        result=dict(bank_count=n,top_k=k,heldout_scenes=16,heldout_images=len(test_y),
                    top1_accuracy=float(correct.float().mean()),topk_coverage=float(included.float().mean()),
                    class_accuracy=by_class,last_loss=float(loss),synthetic_distinct_psfs=True,
                    no_claim_for_current_measured25=True)
    print(json.dumps(result,indent=2))
    assert result['top1_accuracy']>=.9 and result['topk_coverage']>=.95
    return result

def main():
    with tempfile.TemporaryDirectory(prefix='mosr_psf_physical_test_') as tmp:
        results=[run(25,4,Path(tmp)),run(100,8,Path(tmp))]
    print('PHYSICAL_SELECTOR_TEST_PASS',results[0]['top1_accuracy'],results[1]['top1_accuracy'])
if __name__=='__main__':main()
