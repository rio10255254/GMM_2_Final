from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


GMM_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = GMM_ROOT / "Deliverables" / "MOSR_ONNX"
R79 = GMM_ROOT / "Experiments" / "R79_R75v3_DenseMicroscopyScratchGeneralization"
CHECKPOINT = (
    R79
    / "weights"
    / "formal"
    / "seed_752031"
    / "training_progress_LAB_GESR_v1_v5_R75v3_scratch_formal_seed752031_dense_multiscale_e100_20260801_150729"
    / "best_tradeoff.pth.tar"
)
EXPECTED_CHECKPOINT_SHA256 = "7d4b2b3329b7b58338235433e140e542ea7d541b1796e4469ba92c71586ce509"
EXPECTED_ONNX_SHA256 = "35262d5be28839e7082c5a520f4ef351448135ba43e01f1d428b12fab8b64383"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_delivery_module():
    spec = importlib.util.spec_from_file_location("mosr_delivery", PACKAGE / "run.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load delivery module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


class R79FullFrameDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = load_delivery_module()

    def test_exact_r79_checkpoint_and_onnx_are_preserved(self) -> None:
        self.assertEqual(sha256(CHECKPOINT), EXPECTED_CHECKPOINT_SHA256)
        self.assertEqual(sha256(PACKAGE / "model.onnx"), EXPECTED_ONNX_SHA256)

    def test_delivery_has_only_one_full_frame_path(self) -> None:
        source = (PACKAGE / "run.py").read_text(encoding="utf-8")
        self.assertNotIn("--tile-size", source)
        self.assertNotIn("--overlap", source)
        self.assertNotIn("def positions(", source)
        self.assertNotIn("def run_tile(", source)
        self.assertEqual(self.delivery.MAX_SIDE, 2180)
        self.assertEqual(self.delivery.MAX_PIXELS, 3313600)

    def test_source_entrypoint_and_config_use_the_same_contract(self) -> None:
        source = (R79 / "inference" / "infer_r75v3.py").read_text(encoding="utf-8")
        self.assertNotIn("--tile-size", source)
        self.assertNotIn("--overlap", source)
        config = json.loads((R79 / "config" / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual(config["inference"]["mode"], "single_full_frame_only")
        self.assertFalse(config["inference"]["tiling_allowed"])
        self.assertEqual(config["inference"]["maximum_side"], 2180)
        self.assertEqual(config["inference"]["maximum_pixels"], 3313600)

    def test_size_contract_accepts_real_dimensions(self) -> None:
        for shape in ((21, 21), (788, 1024), (1536, 2048), (2180, 1520)):
            self.delivery.validate_image_size(np.zeros(shape, dtype=np.uint8))

    def test_size_contract_rejects_unverified_dimensions(self) -> None:
        rejected = ((20, 21), (21, 20), (2181, 1520), (1600, 2100))
        for shape in rejected:
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                self.delivery.validate_image_size(np.zeros(shape, dtype=np.uint8))

    def test_onnx_keeps_dynamic_full_frame_dimensions(self) -> None:
        session = ort.InferenceSession(str(PACKAGE / "model.onnx"), providers=["CPUExecutionProvider"])
        self.assertEqual(session.get_inputs()[0].shape, ["batch", 1, "height", "width"])
        self.assertEqual(session.get_outputs()[0].shape, ["batch", 1, "height", "width"])

    def test_example_is_unchanged_and_repeatable(self) -> None:
        source = read_gray(PACKAGE / "example" / "input.bmp")
        expected = read_gray(PACKAGE / "example" / "output.bmp")
        model = self.delivery.MosrModel(force_cpu=True)
        first = model.reconstruct(source)
        second = model.reconstruct(source)
        self.assertTrue(np.array_equal(first, expected))
        self.assertTrue(np.array_equal(first, second))


if __name__ == "__main__":
    unittest.main()
