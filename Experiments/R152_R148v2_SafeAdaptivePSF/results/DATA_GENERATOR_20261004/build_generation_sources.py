"""Package the exact historical sources and portable mathematical operations."""
import ast
import hashlib
import json
import pprint
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[4]
PACK = PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004'
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(relative, source):
    path = PACK/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    ast.parse(source, filename=relative)
    path.write_text(source, encoding='utf-8')


def functions(path, names):
    source = Path(path).read_text(encoding='utf-8')
    nodes = {n.name: n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
    return '\n\n'.join(ast.get_source_segment(source, nodes[name]) for name in names)+'\n'


def main():
    historical = {
        'r125_geometry_helper.py': PROJECT/'Experiments/R125_DataAlignedPilot/data/generator_v2.py',
        'r128_scene_generation.py': PROJECT/'Experiments/R128_SourceOnlyFullTraining/data/generator.py',
        'r128_build_all.py': PROJECT/'Experiments/R128_SourceOnlyFullTraining/scripts/build_data.py',
        'r148_physical_views.py': PROJECT/'Experiments/R148_MeasurementStableNativePSF/scripts/prepare_data.py',
        'r148v2_geometry_labels.py': PROJECT/'Experiments/R148v2_HybridContextNativePSF/scripts/prepare_geometry.py',
    }
    expected = {
        'r125_geometry_helper.py':'89a98fe8e5f595691a973b7e699e47fca84eacc822f065155b4880039471bcb5',
        'r128_scene_generation.py':'93f443920148b2d2440e1e19c6d3192eb0adec879644bf404b2c058af458062c',
        'r148_physical_views.py':'42b5410c607e4f7b9321c8f61226abe9d8b246d2ecefe763c26d4dc43a09684b',
    }
    records = {}
    for name, source in historical.items():
        if name in expected:
            assert sha(source) == expected[name], name
        target = PACK/'generation/original_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert source.read_bytes() == target.read_bytes()
        records[name] = {'original_project_path':source.relative_to(PROJECT).as_posix(),
                         'sha256':sha(source), 'delivered_path':target.relative_to(PACK).as_posix()}
    original_cfg = json.loads((PROJECT/'Experiments/R128_SourceOnlyFullTraining/config/study.json').read_text(encoding='utf-8'))
    cfg = {k:original_cfg[k] for k in ('splits','split_seeds','categories','category_weights','native_field','render_factor','latent_factor')}
    write('generation/__init__.py', '"""Deterministic original-scene and measured-PSF image generation."""\n')
    write('generation/recipe.py', '"""The original fixed scene counts, seed streams and shape proportions."""\nSCENE_CONFIG = '+pprint.pformat(cfg,sort_dicts=False)+'\nTESTED_VERSIONS = '+pprint.pformat({'numpy':'1.26.4','scipy':'1.13.1','Pillow':'10.4.0'})+'\n')
    write('generation/source_history.py', '"""Exact historical sources. Use generate_data.py for independent execution.\n\noriginal_sources preserves the unchanged historical programs for audit.\nTheir old launch/configuration environment is not an execution dependency.\nThe active modules retain their numerical functions with local imports.\n"""\nSOURCES = '+pprint.pformat(records,width=110,sort_dicts=False)+'\n')
    write('generation/geometry.py', '"""Unchanged geometry functions from the original R125 helper."""\nimport math\nimport numpy as np\n\n'+functions(historical['r125_geometry_helper.py'], ['area_average','_parameters','object_score']))
    write('generation/scene.py', '"""Unchanged scene parameters/intensity functions from the R128 source."""\nimport math\nimport hashlib\nimport json\nimport numpy as np\nfrom . import geometry as g\nfrom .recipe import SCENE_CONFIG as CFG\n\n'+functions(historical['r128_scene_generation.py'], ['digest','canonical','categories','parameters','optical'])+'''

def render_initial_latent(metadata, native_rows=16):
    """Render the only R128 latent view consumed by the R148/R152 recipe.

    Exactly the original 8x cell coordinates, intensity math, 2x area means
    and float32 rounding. Row chunks only reduce temporary memory. The unused
    old second view, simulated Gaussian blur and diagnostic arrays are omitted.
    """
    n = CFG['native_field']
    axis = (np.arange(n*8, dtype=float)+.5)/8-n/2
    latent = np.empty((n*4,n*4), dtype=np.float32)
    for first in range(0,n,native_rows):
        last = min(n,first+native_rows)
        image, _ = optical(axis[None,:], axis[first*8:last*8,None], metadata, [0.,0.])
        if metadata['category'] == 'clean_identity':
            target = g.area_average(image,8).astype(np.float32)
            target = np.rint(target*255).astype(np.uint8).astype(np.float32)/np.float32(255)
            values = target.repeat(4,0).repeat(4,1)
        else:
            values = g.area_average(image,2).astype(np.float32)
        latent[first*4:last*4] = values
    return latent
''')
    optical_functions = functions(historical['r148_physical_views.py'], ['digest_array','bank4','shift4','avg4','convolve4','specs'])
    optical_functions = optical_functions.replace("ROOT/'calibration/measured_psf_bank.npz'", "ROOT/'calibration/psf25_bank.npz'")
    write('generation/physical_views.py', '"""Original R148 physical views, using the package-local PSF bank."""\nimport hashlib\nimport numpy as np\nfrom scipy.interpolate import RectBivariateSpline\nfrom scipy.signal import fftconvolve\nfrom settings import ROOT\n\nSPLIT_OFFSET={\'train\':0,\'dev\':7,\'test\':13}\nSUB=(.25,.5,.75)\nLARGE=(2.,4.,6.,8.)\nDIR=((1,0),(0,1),(-1,0),(0,-1))\nCONTRAST=(.85,.95,1.,1.15)\nBRIGHT=(-5.,0.,3.,5.)\nNOISE=(.5,1.,1.5,3.)\n_BANK4=None\n\n'+optical_functions+'''

def generate_views(latent_float32, metadata):
    """Same photometric headroom, shifts, measured blur and historical rounding."""
    latent = latent_float32.astype(np.float64)
    mid = (metadata['photometry']['low_gray']+metadata['photometry']['high_gray'])/(2*255)
    targets=[]
    noiseless=[]
    views=specs(metadata['split'],metadata['index'],metadata['category'])
    clips=[]
    kernels=bank4()
    for v in views:
        requested_contrast=v['contrast'];requested_brightness=v['brightness_gray']
        span=float(latent.max()-latent.min())
        effective_contrast=min(requested_contrast,.996/max(span,1e-9))
        base=mid+effective_contrast*(latent-mid)
        lower=.002-float(base.min());upper=.998-float(base.max())
        offset=float(np.clip(requested_brightness/255,lower,upper))
        v['requested_contrast']=requested_contrast;v['requested_brightness_gray']=requested_brightness
        v['contrast']=effective_contrast;v['brightness_gray']=offset*255
        clear=base+offset;clips.append(float(((clear<0)|(clear>1)).mean()))
        clear=np.clip(clear,0,1);clear=shift4(clear,*v['shift_xy'])
        targets.append(avg4(clear))
        blurred=clear if v['psf_index']<0 else convolve4(clear,kernels[v['psf_index']])
        noiseless.append(avg4(blurred))
    if max(clips) != 0:
        raise RuntimeError('Original no-clipping contract failed')
    return {'target':np.stack(targets).astype(np.float16),
            'noiseless':np.stack(noiseless).astype(np.float16)},views
''')
    write('generation/labels.py', '''"""Original R148v2 material-boundary coordinates, with package-local geometry."""
import numpy as np
from . import geometry as g


def generate_labels(shape, category, views):
    axis=np.arange(144,240,dtype=float)+.5-192
    y,x=axis[:,None],axis[None,:]
    sdfs=[]
    valid=[]
    for view in views:
        score=g.object_score(x,y,shape,view['shift_xy'])
        gy,gx=np.gradient(score)
        distance=np.clip(score/(np.hypot(gx,gy)+1e-4),-8,8)
        sdfs.append(distance.astype(np.float16))
        valid.append(category!='flat_negative')
    return {'sdf':np.stack(sdfs),'valid':np.asarray(valid,dtype=np.uint8)}
''')
    lineage = []
    manifest = json.loads((PROJECT/'Experiments/R147_FullResPSFConsistency/data/manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['entries']:
        source = Path(entry['original_metadata']['path'])
        original = json.loads(source.read_text(encoding='utf-8'))
        assert sha(source) == entry['original_metadata']['sha256']
        assert original['generator_sha256'] == expected['r128_scene_generation.py']
        assert original['geometry_helper_sha256'] == expected['r125_geometry_helper.py']
        kept = {k:original[k] for k in ('parent_id','split','index','seed','category','shape','photometry','psf','shift_xy','noise_sigma_gray','motion_observable','geometry_sha256','external_source_inputs','real_or_SEM_answers_used')}
        digest = hashlib.sha256(json.dumps(kept,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        lineage.append({'split':entry['split'],'index':entry['index'],
                        'seed_parameter_sha256':digest,
                        'original_metadata_sha256':sha(source)})
    lineage.sort(key=lambda e:({'train':0,'dev':1,'test':2}[e['split']],e['index']))
    write('generation/lineage.py', '"""Locked reference identities for independently regenerated seed parameters."""\nPARENTS = '+pprint.pformat(lineage,width=115,sort_dicts=False)+'\n')
    (OUT/'historical_sources.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Portable numerical modules and five exact historical sources packaged.',flush=True)


if __name__ == '__main__':
    main()
