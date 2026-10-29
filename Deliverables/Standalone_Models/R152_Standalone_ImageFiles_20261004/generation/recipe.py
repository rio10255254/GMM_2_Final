"""The original fixed scene counts, seed streams and shape proportions."""
SCENE_CONFIG = {'splits': {'train': 512, 'dev': 128, 'test': 128},
 'split_seeds': {'train': 128100000, 'dev': 128200000, 'test': 128300000},
 'categories': ['irregular_curved',
                'corners_lines_junctions',
                'dense_close_structures',
                'textured_edges',
                'clean_identity',
                'noisy_identity',
                'flat_negative'],
 'category_weights': [0.2, 0.2, 0.2, 0.2, 0.05, 0.05, 0.1],
 'native_field': 384,
 'render_factor': 8,
 'latent_factor': 4}
TESTED_VERSIONS = {'Pillow': '10.4.0', 'numpy': '1.26.4', 'scipy': '1.13.1'}
