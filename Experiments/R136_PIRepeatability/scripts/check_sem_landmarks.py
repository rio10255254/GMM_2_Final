exec(open(__file__.replace('check_sem_landmarks.py','locate_sem_field.py'),encoding='utf-8').read().split('res=cv2.matchTemplate')[0])
scale=28.9330637762/134.46805205
sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=.015)
kp2,des2=sift.detectAndCompute(new,None);records=[]
for flip in [False,True]:
 im=old[:,::-1] if flip else old;im=cv2.resize(im,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
 kp1,des1=sift.detectAndCompute(im,None);matches=cv2.BFMatcher(crossCheck=True).match(des1,des2);good=[a for a in matches if a.distance<250]
 src=np.array([kp1[m.queryIdx].pt for m in good]);dst=np.array([kp2[m.trainIdx].pt for m in good])
 M,inlier=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=2,maxIters=10000)
 yes=inlier.ravel().astype(bool);err=np.linalg.norm(src@M[:,:2].T+M[:,2]-dst,axis=1)
 record=dict(flip=flip,matches=len(good),inliers=int(yes.sum()),median_error_px=float(np.median(err[yes])),matrix=M.tolist(),source_inliers=src[yes].tolist(),target_inliers=dst[yes].tolist());records.append(record)
 canvas=cv2.drawMatches(im,kp1,new,kp2,[g for g,j in zip(good,yes) if j],None,flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
 cv2.imwrite(str(O/f'landmarks_flip{flip}.jpg'),canvas)
print(json.dumps([{k:v for k,v in r.items() if 'inliers' not in k or k=='inliers'} for r in records],indent=2))
(O/'landmark_check.json').write_text(json.dumps(records,indent=2),encoding='utf-8')

