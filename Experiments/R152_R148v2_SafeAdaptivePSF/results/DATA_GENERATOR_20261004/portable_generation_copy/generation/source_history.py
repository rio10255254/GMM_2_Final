"""Exact historical sources. Use generate_data.py for independent execution.

original_sources preserves the unchanged historical programs for audit.
Their old launch/configuration environment is not an execution dependency.
The active modules retain their numerical functions with local imports.
"""
SOURCES = {'r125_geometry_helper.py': {'original_project_path': 'Experiments/R125_DataAlignedPilot/data/generator_v2.py',
                             'sha256': '89a98fe8e5f595691a973b7e699e47fca84eacc822f065155b4880039471bcb5',
                             'delivered_path': 'generation/original_sources/r125_geometry_helper.py'},
 'r128_scene_generation.py': {'original_project_path': 'Experiments/R128_SourceOnlyFullTraining/data/generator.py',
                              'sha256': '93f443920148b2d2440e1e19c6d3192eb0adec879644bf404b2c058af458062c',
                              'delivered_path': 'generation/original_sources/r128_scene_generation.py'},
 'r128_build_all.py': {'original_project_path': 'Experiments/R128_SourceOnlyFullTraining/scripts/build_data.py',
                       'sha256': 'e96c4c3f3768919489b142de8f799108c6cce37173bab6ea33f1176733ce4e4f',
                       'delivered_path': 'generation/original_sources/r128_build_all.py'},
 'r148_physical_views.py': {'original_project_path': 'Experiments/R148_MeasurementStableNativePSF/scripts/prepare_data.py',
                            'sha256': '42b5410c607e4f7b9321c8f61226abe9d8b246d2ecefe763c26d4dc43a09684b',
                            'delivered_path': 'generation/original_sources/r148_physical_views.py'},
 'r148v2_geometry_labels.py': {'original_project_path': 'Experiments/R148v2_HybridContextNativePSF/scripts/prepare_geometry.py',
                               'sha256': '784f9f23bb625cb46e1c921faf816e11298557549cd43d2962cc34b40579be52',
                               'delivered_path': 'generation/original_sources/r148v2_geometry_labels.py'}}
