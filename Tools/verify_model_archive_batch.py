"""Verify every downloaded object and inspect trusted saved states on CPU.

Only a newly created, owned buffer directory is used. The buffer is overwritten
after each exact object has been verified and its inspection recorded; research
originals are never opened or changed. Historical model failures are retained.
"""
import argparse,gzip,gc,json,os,hashlib,sys,time,zipfile
from pathlib import Path
from research_recovery import digest,write_json
from verify_research_checkpoint_history import summarize

def inspect_data_format(path,relative):
    import numpy as np
    suffix=Path(relative).suffix.lower()
    try:
        if suffix=='.npy':
            with path.open('rb') as stream:
                version=np.lib.format.read_magic(stream)
                shape,fortran,dtype=np.lib.format._read_array_header(stream,version)
            return {'format_status':'NUMPY_HEADER_READABLE','shape':list(shape),'dtype':str(dtype),'fortran_order':bool(fortran)}
        if suffix=='.npz':
            arrays=[]
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if not info.filename.endswith('.npy'):continue
                    with archive.open(info) as stream:
                        version=np.lib.format.read_magic(stream);shape,fortran,dtype=np.lib.format._read_array_header(stream,version)
                    arrays.append({'name':info.filename,'shape':list(shape),'dtype':str(dtype)})
            return {'format_status':'NUMPY_ARCHIVE_HEADERS_READABLE','arrays':arrays}
        if suffix in {'.bmp','.png','.jpg','.jpeg','.tif','.tiff','.webp','.gif'}:
            import cv2
            image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_UNCHANGED)
            if image is None:return {'format_status':'IMAGE_DECODE_FAILURE_PRESERVED'}
            return {'format_status':'IMAGE_DECODED','shape':list(image.shape),'dtype':str(image.dtype)}
        if suffix=='.mat':
            import scipy.io
            return {'format_status':'MATLAB_VARIABLE_HEADERS_READABLE','variables':[{'name':name,'shape':list(shape),'type':kind} for name,shape,kind in scipy.io.whosmat(path)]}
        return {'format_status':'EXACT_BYTES_PRESERVED_FORMAT_NOT_APPLICABLE'}
    except Exception as error:return {'format_status':'HISTORICAL_FORMAT_OR_ENVIRONMENT_FAILURE_RECORDED','format_error_type':type(error).__name__}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True);p.add_argument('--buffer-dir',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--inspect-data-formats',action='store_true');a=p.parse_args()
    if a.report.exists() or a.buffer_dir.exists():raise FileExistsError('Use new batch validation paths')
    a.buffer_dir.mkdir(parents=True);buffer=a.buffer_dir/'verified_object.pth.tar'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(1)
    if torch.version.cuda is not None:raise ValueError('Use the verified CPU-only environment')
    with gzip.open(a.manifest,'rt',encoding='utf-8') as stream:m=json.load(stream)
    objects={};groups={}
    for row in m['files']:
        previous=objects.setdefault(row['sha256'],row)
        if previous['bytes']!=row['bytes']:raise ValueError('Conflicting object byte counts')
        groups.setdefault(row['asset'],{})[row['sha256']]=row
    checked=[];assets=[];started=time.time()
    for spec in m['assets']:
        if Path(spec['name']).name!=spec['name']:raise ValueError('Invalid part name')
        path=a.assets/spec['name']
        if path.stat().st_size!=spec['bytes'] or digest(path)!=spec['sha256']:raise ValueError('Downloaded archive differs from recorded GitHub content')
        with zipfile.ZipFile(path) as archive:
            expected=groups.pop(spec['name'])
            if set(archive.namelist())!={'objects/'+value for value in expected} or len(archive.namelist())!=len(expected):raise ValueError('Archive members differ from declared unique objects')
            for sha,row in expected.items():
                h=hashlib.sha256();size=0
                with archive.open('objects/'+sha) as source,buffer.open('wb') as output:
                    while block:=source.read(4*1024**2):h.update(block);size+=len(block);output.write(block)
                if h.hexdigest()!=sha or size!=row['bytes'] or digest(buffer)!=sha:raise ValueError('Restored original object differs')
                record={'sha256':sha,'bytes':size,'original_project_path':row.get('original_project_path',row['path']),
                  'scope':row.get('scope'),'exact_file_bytes_restored':True}
                if row['path'].lower().endswith(('.pth.tar','.pt','.pth','.ckpt')):
                    try:
                        value=torch.load(buffer,map_location='cpu',weights_only=False)
                        record.update(summarize(value,torch));record['load_status']='LOADABLE';del value;gc.collect()
                    except Exception as error:record['load_status']='LOAD_ERROR_PRESERVED';record['error_type']=type(error).__name__
                else:
                    record['load_status']='NON_TORCH_FORMAT_PRESERVED_NO_TORCH_CLAIM'
                    if a.inspect_data_formats:record.update(inspect_data_format(buffer,row['path']))
                checked.append(record)
                if len(checked)%20==0:print('DOWNLOADED_MODEL_OBJECTS_RESTORED_INSPECTED',len(checked),len(objects),flush=True)
        assets.append(spec)
    if groups or len(checked)!=len(objects):raise ValueError('An object or part was not checked')
    write_json(a.report,{'status':'PASS_FILE_IDENTITY_AND_RESTORATION','device':'cpu','torch':torch.__version__,
      'torch_cuda_build':torch.version.cuda,'unique_objects_restored':len(checked),'checks':checked,'assets':assets,
      'load_errors_preserved':sum(r['load_status']=='LOAD_ERROR_PRESERVED' for r in checked),
      'nonfinite_histories_preserved':sum(r.get('all_tensors_finite') is False for r in checked),
      'inference_repeated':False,'training_repeated':False,'research_originals_changed':False,
      'buffer_owned_by_this_verification':str(buffer),'buffer_bytes':buffer.stat().st_size if buffer.exists() else 0,'seconds':time.time()-started})
    print('MODEL_BATCH_ALL_GITHUB_OBJECTS_RESTORED_VERIFIED',len(checked),flush=True)

if __name__=='__main__':main()
