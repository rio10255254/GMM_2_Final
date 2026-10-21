"""Check recovered ONNX files and execute explicit CPU-only deployment examples.

The input is a fixed crop of a separately verified camera-source frame. Parsing,
CPU execution and file identity are checked; native-model numerical equivalence,
whole-frame/tiled measurement parity and scientific performance are not inferred.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from research_recovery import digest, safe_relative, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    for record in manifest['files']:
        path = args.root / safe_relative(record['path'])
        if (path.stat().st_size, digest(path)) != (record['bytes'], record['sha256']):
            raise ValueError('A recovered graph or camera-source input differs')
    if args.output.exists():
        raise FileExistsError('Use a new owned graph-inspection output directory')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import cv2
    import numpy as np
    import onnx
    import onnxruntime as ort
    cv2.setNumThreads(1)
    raw = cv2.imdecode(np.fromfile(args.root / safe_relative(manifest['camera_source']), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim != 2 or raw.dtype != np.uint8:
        raise ValueError('The frozen original camera-source example must be grayscale 8-bit')
    args.output.mkdir(parents=True)
    reports = []
    for row in manifest['graphs']:
        path = args.root / safe_relative(row['path'])
        model = onnx.load(str(path), load_external_data=False)
        if any(tensor.data_location == onnx.TensorProto.EXTERNAL for tensor in model.graph.initializer):
            raise ValueError('The graph needs explicitly preserved external weight files')
        onnx.checker.check_model(model, full_check=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(model.SerializeToString(), sess_options=options, providers=['CPUExecutionProvider'])
        inputs = session.get_inputs()
        if len(inputs) != 1 or inputs[0].type != 'tensor(float)' or len(inputs[0].shape) != 4:
            raise ValueError('Review this deployment graph input interface explicitly')
        shape = [dimension if isinstance(dimension, int) and dimension > 0 else (1 if index < 2 else 256)
                 for index, dimension in enumerate(inputs[0].shape)]
        if shape[:2] != [1, 1] or shape[2] > raw.shape[0] or shape[3] > raw.shape[1]:
            raise ValueError('The explicit camera crop does not fit this graph interface')
        height, width = shape[2:]
        x = (raw.shape[1] - width) // 2
        y = (raw.shape[0] - height) // 2
        value = np.ascontiguousarray(raw[y:y+height, x:x+width].astype(np.float32)[None, None] / 255.0)
        outputs = session.run(None, {inputs[0].name: value})
        items = []
        for number, prediction in enumerate(outputs):
            if not np.issubdtype(prediction.dtype, np.number) or not np.isfinite(prediction).all():
                raise ValueError('Nonfinite or nonnumeric deployment output')
            np.save(args.output / (row['id'] + '_output_' + str(number) + '.npy'), prediction, allow_pickle=False)
            items.append({'shape': list(prediction.shape), 'dtype': str(prediction.dtype),
                          'all_values_finite': True, 'minimum': float(prediction.min()), 'maximum': float(prediction.max()),
                          'exact_array_sha256': hashlib.sha256(prediction.tobytes()).hexdigest()})
        record = {'id': row['id'], 'original_path': row['original_path'], 'graph_sha256': digest(path),
                  'onnx_graph_checker_passed': True, 'opset_imports': [{'domain': item.domain, 'version': item.version} for item in model.opset_import],
                  'CPU_execution_providers': session.get_providers(), 'input_shape': shape, 'source_crop_xywh': [x, y, width, height],
                  'input_float32_sha256': hashlib.sha256(value.tobytes()).hexdigest(), 'outputs': items,
                  'declared_historical_role': row['historical_role'], 'native_model_parity_claimed': False}
        if record['CPU_execution_providers'] != ['CPUExecutionProvider']:
            raise ValueError('A non-CPU provider was selected')
        reports.append(record)
    wrapper = None
    if manifest.get('original_wrapper'):
        spec = importlib.util.spec_from_file_location('recovered_original_R61_ONNX_wrapper', args.root / safe_relative(manifest['original_wrapper']))
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
        original = native.read_image(args.root / safe_relative(manifest['original_wrapper_input']))
        expected_path = args.root / safe_relative(manifest['original_wrapper_reference'])
        expected = native.read_image(expected_path)
        model = native.MosrModel(force_cpu=True)
        actual = model.reconstruct(original, 0, 192, 1)
        destination = args.output / 'R61_original_package_example.bmp'
        native.write_bmp(destination, actual)
        if actual.shape != expected.shape:
            raise ValueError('The original package example output size differs')
        difference = np.abs(actual.astype(np.int16) - expected.astype(np.int16))
        wrapper = {'original_package_wrapper_and_optical_constants_executed': True,
                   'provider': model.provider, 'full_image_processing': True, 'tiled_mode_repeated': False,
                   'original_example_reference_bmp_sha256': digest(expected_path),
                   'actual_bmp_sha256': digest(destination), 'reference_BMP_exact': digest(destination) == digest(expected_path),
                   'maximum_pixel_difference': int(difference.max()), 'mean_pixel_difference': float(difference.mean()),
                   'independent_physical_validation_or_new_camera_acquisition': False}
        if model.provider != 'CPUExecutionProvider':
            raise ValueError('The original wrapper selected a non-CPU provider')
    report = {'status': 'PASS_RECOVERED_GRAPH_FORMAT_AND_EXPLICIT_CPU_EXECUTION', 'graphs': reports,
              'original_R61_package_wrapper': wrapper,
              'onnx_version': onnx.__version__, 'onnxruntime_version': ort.__version__,
              'source_input_sha256': digest(args.root / safe_relative(manifest['camera_source'])),
              'GPU_or_training_used': False, 'historical_model_files_modified': False,
              'native_network_or_tiling_measurement_equivalence_claimed': False, 'whole_project_complete': False}
    write_json(args.output / 'RECOVERED_ONNX_GRAPHS_VERIFIED.json', report)
    print('RECOVERED_ORIGINAL_DEPLOYMENT_GRAPHS_CPU_CHECKED', len(reports), flush=True)


if __name__ == '__main__':
    main()
