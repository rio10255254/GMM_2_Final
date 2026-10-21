"""Recheck saved PSF spectra from their original crops and float Wiener arrays.

Only the two original pure FFT functions execute. The historical figure-writing
entry point is never run, so no thesis image or result is replaced. This checks
saved spectra, not PSF fitting, neural inference, or historical training.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import loadmat

from research_recovery import safe_relative, write_json


BASE = 'Thesis_MOSR_Evidence/Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/01_global_bads_fit'
SOURCE = BASE+'/source_data/center9_pillar_fit_20x_50x'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():
        raise FileExistsError('Retain the previous replay receipt')
    manifest=args.root/'docs/reproducibility/optical_calibration/SPECTRUM_SOURCE_FILES.json'
    expected=json.loads(manifest.read_text(encoding='utf-8'))
    for row in expected['files']:
        path=args.root/safe_relative(row['path'])
        with path.open('rb') as stream:
            checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        if (path.stat().st_size,checksum)!=(row['bytes'],row['sha256']):
            raise ValueError('An original saved-spectrum source differs: '+row['path'])
    source=args.root/(SOURCE+'/spectra/generate_absolute_spectra.py')
    names={'absolute_fft_amplitude_array','absolute_fft_amplitude'}
    nodes=[node for node in ast.parse(source.read_text(encoding='utf-8')).body
           if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes}!=names:
        raise ValueError('The required original FFT functions are missing')
    namespace={'np':np,'Image':Image,'Path':Path}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
    checks=[]
    for magnification in ['20x','50x']:
        figures=args.root/(BASE+'/figures/center9_pillar_fit_20x_50x/'+magnification)
        wiener=loadmat(args.root/(SOURCE+'/psf_deconvolution_cd/'+magnification+'_wiener_deconvolution.mat'))
        nsr=float(np.asarray(wiener['nsr']).squeeze())
        if not np.isclose(nsr,0.05):
            raise ValueError('The recorded current Wiener setting is not 0.05')
        values={}
        for label,filename in [('captured','05_original_pillar_3x3.bmp'),
                               ('v42','06_v42_e120_reconstruction_pillar_3x3.bmp')]:
            amplitude,dbfs=namespace['absolute_fft_amplitude'](figures/filename)
            values[label+'_amplitude']=amplitude;values[label+'_dbfs']=dbfs
        amplitude,dbfs=namespace['absolute_fft_amplitude_array'](wiener['restored'])
        values['deconvolved_amplitude']=amplitude;values['deconvolved_dbfs']=dbfs
        shape=values['captured_amplitude'].shape
        if any(values[key].shape!=shape for key in values):
            raise ValueError('The three current sources have different image extents')
        values['fx_cycles_per_pixel']=np.fft.fftshift(np.fft.fftfreq(shape[1]))
        values['fy_cycles_per_pixel']=np.fft.fftshift(np.fft.fftfreq(shape[0]))
        with np.load(args.root/(SOURCE+'/spectra/'+magnification+'_absolute_spectra.npz'),allow_pickle=False) as original:
            if set(original.files)!=set(values):
                raise ValueError('The saved spectrum fields differ')
            for field,value in values.items():
                if not np.array_equal(original[field],value):
                    raise ValueError('Recomputed spectrum differs: '+magnification+'/'+field)
                checks.append({'magnification':magnification,'field':field,'shape':list(value.shape),
                               'values':int(value.size),'exact_original_values':True})
    write_json(args.report,{'status':'PASS_EXACT_ORIGINAL_SPECTRUM_ARRAYS',
        'verified_source_files':len(expected['files']),'arrays':len(checks),
        'numeric_values':sum(row['values'] for row in checks),'checks':checks,
        'historical_figures_or_inputs_modified':False,'PSF_fitting_repeated':False,
        'neural_inference_or_training_repeated':False,
        'old_0_08_figures_recomputed':False})
    print('ORIGINAL_SPECTRUM_ARRAYS_REPLAY_VERIFIED',len(checks),sum(row['values'] for row in checks),flush=True)


if __name__=='__main__':
    main()
