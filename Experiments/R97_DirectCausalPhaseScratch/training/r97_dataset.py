"""Hash-locked procedural loader with direct applied-correction targets for R97."""
from __future__ import annotations

from collections import defaultdict
import importlib.util
import math
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, Sampler


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REPLAY = _load("r97_dataset_replay", ROOT / "training" / "causal_stage_replay.py")
TARGETS = _load("r97_dataset_targets", ROOT / "training" / "counterfactual_targets.py")


def warp_u8(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return np.asarray(array)
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        np.asarray(array), matrix, (array.shape[1], array.shape[0]),
        flags=interpolation, borderMode=cv2.BORDER_REFLECT_101,
    )


def _as_float(rows: list[np.ndarray]) -> torch.Tensor:
    return torch.from_numpy(np.stack(rows)).unsqueeze(1).float().div_(255.0)


def _as_layer(rows: list[np.ndarray]) -> torch.Tensor:
    return torch.from_numpy(np.stack(rows)).unsqueeze(1).float()


class R97SceneDataset(Dataset):
    """Deterministic scene crops with same-scene T/B/S and exact branch truth."""

    def __init__(
        self,
        package: Path,
        manifest: dict[str, Any],
        split: str,
        patch_size: int,
        core_size: int,
        epoch: int,
        *,
        all_observations: bool = False,
        master_seed: int = 960041,
        role_cycle: int = 0,
    ):
        self.package = Path(package)
        self.records = [row for row in manifest["records"] if row["split"] == split]
        self.records.sort(key=lambda row: int(row["scene_index"]))
        self.patch_size = int(patch_size)
        self.core_size = int(core_size)
        self.canvas_size = int(manifest["canvas_size"])
        self.epoch = int(epoch)
        self.all_observations = bool(all_observations)
        self.master_seed = int(master_seed)
        self.role_cycle = int(role_cycle)
        self._hidden_cache: dict[tuple[int, int], dict[str, Any]] = {}
        self.items: list[tuple[dict[str, Any], tuple[int, ...] | None]] = []
        for record in self.records:
            if not self.all_observations:
                self.items.append((record, None))
            elif record["role"] == "signed_subpixel_motion":
                self.items.extend(((record, (0, 1)), (record, (0, 2)), (record, (0, 3))))
            elif record["role"] in {"exposure_coherent_bundle", "persistent_detail_bundle"}:
                self.items.append((record, (0, 1, 2, 3)))
            else:
                self.items.extend((record, (index, index)) for index in range(4))
        if self.patch_size > self.canvas_size or self.patch_size % 8 or self.core_size % 8:
            raise ValueError("Patch/core must fit and align to eight pixels")
        if self.patch_size < self.core_size or (self.patch_size - self.core_size) % 2:
            raise ValueError("Invalid patch/core pair")

    def __len__(self) -> int:
        return len(self.items)

    def set_role_cycle(self, cycle: int) -> None:
        self.role_cycle = int(cycle)

    def role_at(self, index: int) -> str:
        return str(self.items[index][0]["role"])

    def view_count_at(self, index: int) -> int:
        record, fixed = self.items[index]
        if fixed is not None:
            return len(fixed)
        return 2

    @staticmethod
    def _aligned_random(rng: np.random.Generator, maximum: int) -> int:
        return int(rng.integers(0, maximum // 8 + 1)) * 8

    def _random_origins(self, scene_index: int) -> np.ndarray:
        rng = np.random.default_rng(
            self.master_seed * 1000003 + scene_index * 10007 + self.epoch * 7919 + self.patch_size * 17
        )
        maximum = self.canvas_size - self.patch_size
        y0 = self._aligned_random(rng, maximum)
        x0 = self._aligned_random(rng, maximum)
        maximum_offset = max(8, min(self.core_size // 2, maximum))
        choices = np.arange(8, maximum_offset + 1, 8, dtype=np.int32)
        for _ in range(32):
            dy = int(rng.choice(choices)) * int(rng.choice([-1, 1]))
            dx = int(rng.choice(choices)) * int(rng.choice([-1, 1]))
            y1 = int(np.clip(y0 + dy, 0, maximum) // 8 * 8)
            x1 = int(np.clip(x0 + dx, 0, maximum) // 8 * 8)
            if y1 != y0 or x1 != x0:
                return np.asarray([[y0, x0], [y1, x1]], dtype=np.int64)
        y1 = min(maximum, y0 + min(64, max(0, maximum - y0))) // 8 * 8
        if y1 == y0:
            y1 = max(0, y0 - min(64, y0)) // 8 * 8
        return np.asarray([[y0, x0], [y1, x0]], dtype=np.int64)

    def _structure_origin(self, mask: np.ndarray, scene_index: int) -> tuple[int, int, float, int]:
        maximum = self.canvas_size - self.patch_size
        binary = mask >= 128
        boundary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        if maximum <= 0:
            return 0, 0, float(np.mean(binary)), int(np.count_nonzero(boundary))
        coordinates = np.argwhere(boundary > 0)
        if not len(coordinates):
            coordinates = np.argwhere(binary)
        if not len(coordinates):
            raise RuntimeError("Empty procedural mask")
        rng = np.random.default_rng(
            self.master_seed * 1000033 + scene_index * 10009 + self.epoch * 7937 + self.patch_size * 19
        )
        best: tuple[float, int, int, float, int] | None = None
        for candidate in rng.permutation(len(coordinates))[: min(96, len(coordinates))]:
            cy, cx = coordinates[int(candidate)]
            y0 = int(np.clip(int(cy) - self.patch_size // 2, 0, maximum) // 8 * 8)
            x0 = int(np.clip(int(cx) - self.patch_size // 2, 0, maximum) // 8 * 8)
            crop = binary[y0:y0 + self.patch_size, x0:x0 + self.patch_size]
            edge = boundary[y0:y0 + self.patch_size, x0:x0 + self.patch_size]
            fraction = float(np.mean(crop))
            count = int(np.count_nonzero(edge))
            penalty = max(0.05 - fraction, 0.0) + max(fraction - 0.95, 0.0)
            penalty += max(256 - count, 0) / 256.0
            row = (penalty, y0, x0, fraction, count)
            if best is None or row[0] < best[0]:
                best = row
            if penalty <= 0:
                break
        assert best is not None
        return int(best[1]), int(best[2]), float(best[3]), int(best[4])

    def _observation_indices(self, record: dict[str, Any], fixed: tuple[int, ...] | None) -> tuple[tuple[int, ...], int]:
        scene_index = int(record["scene_index"])
        role = str(record["role"])
        if fixed is not None:
            indices = fixed
        elif role == "exposure_coherent_bundle":
            # Rotate through the full four-step path without making one update
            # four times larger than every other scene.
            indices = (0, 3) if (self.epoch + scene_index + self.role_cycle) % 2 == 0 else (1, 2)
        elif role == "persistent_detail_bundle":
            indices = (0, 2) if (self.epoch + scene_index + self.role_cycle) % 2 == 0 else (1, 3)
        elif role == "signed_subpixel_motion":
            selector = (self.epoch + scene_index + self.role_cycle) % 4
            indices = (0, 3) if selector == 0 else ((0, 1) if selector % 2 else (0, 2))
        else:
            first = (self.epoch + scene_index + self.role_cycle) % 4
            indices = (first, (first + 1 + scene_index % 2) % 4)
        if role == "signed_subpixel_motion":
            pair_kind = 1
        elif role == "exposure_coherent_bundle":
            pair_kind = 3
        elif role == "persistent_detail_bundle":
            pair_kind = 4
        else:
            pair_kind = 2
        return tuple(int(i) for i in indices), pair_kind

    def __getitem__(self, index: int) -> dict[str, Any]:
        record, fixed = self.items[index]
        scene_index = int(record["scene_index"])
        observation_indices, pair_kind = self._observation_indices(record, fixed)
        target_base = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_base = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        if pair_kind in {1, 3, 4} or record["role"] in {"difficult_boundary_anti_halo", "severe_recoverable"}:
            y0, x0, foreground_fraction, boundary_pixels = self._structure_origin(np.asarray(mask_base), scene_index)
            origins = np.repeat(np.asarray([[y0, x0]], dtype=np.int64), len(observation_indices), axis=0)
        else:
            origins = self._random_origins(scene_index)
            y0, x0 = origins[0]
            crop = np.asarray(mask_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size]) >= 128
            edge = cv2.morphologyEx(crop.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
            foreground_fraction = float(np.mean(crop))
            boundary_pixels = int(np.count_nonzero(edge))

        source_rows: list[np.ndarray] = []
        noise_free_rows: list[np.ndarray] = []
        target_rows: list[np.ndarray] = []
        mask_rows: list[np.ndarray] = []
        optical_rows: list[np.ndarray] = []
        support_rows: list[np.ndarray] = []
        branch_rows: dict[str, list[np.ndarray]] = defaultdict(list)
        motions: list[tuple[float, float]] = []
        identities: list[bool] = []
        recoverability: list[float] = []
        exposure_positions: list[float] = []

        for view, observation_index in enumerate(observation_indices):
            observation = record["observations"][observation_index]
            dx = float(observation["motion_dx_px"])
            dy = float(observation["motion_dy_px"])
            y0, x0 = (int(value) for value in origins[view])
            margin = 24
            ys = max(0, y0 - margin)
            xs = max(0, x0 - margin)
            ye = min(self.canvas_size, y0 + self.patch_size + margin)
            xe = min(self.canvas_size, x0 + self.patch_size + margin)
            target_window = np.asarray(target_base[ys:ye, xs:xe])
            mask_window = np.asarray(mask_base[ys:ye, xs:xe])
            target_warped = warp_u8(target_window, dx, dy, cv2.INTER_LANCZOS4)
            mask_warped = warp_u8(mask_window, dx, dy, cv2.INTER_LINEAR)
            local_y, local_x = y0 - ys, x0 - xs
            target_u8 = np.asarray(target_warped[local_y:local_y + self.patch_size, local_x:local_x + self.patch_size]).copy()
            mask_u8 = np.asarray(mask_warped[local_y:local_y + self.patch_size, local_x:local_x + self.patch_size]).copy()
            source = np.load(self.package / observation["source"], mmap_mode="r", allow_pickle=False)
            noise_free = np.load(self.package / observation["noise_free_source"], mmap_mode="r", allow_pickle=False)
            source_u8 = np.asarray(source[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy()
            noise_free_u8 = np.asarray(noise_free[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy()
            cache_key = (scene_index, int(observation_index))
            hidden = self._hidden_cache.get(cache_key)
            if hidden is None:
                hidden = REPLAY.recover_hidden_parameters(
                    observation["degradation"], int(observation["degradation_parameter_seed"]),
                    (self.canvas_size, self.canvas_size),
                )
                if observation["degradation"].get("requested_source_contrast_gray") is not None:
                    replayed = REPLAY.replay_causal_stages(
                        np.asarray(target_base), np.asarray(mask_base), observation["degradation"],
                        int(observation["degradation_parameter_seed"]),
                    )
                    hidden = replayed.hidden_parameters
                self._hidden_cache[cache_key] = hidden
            layers = REPLAY.decompose_optical_layers(
                target_u8, mask_u8, record["texture"], observation["degradation"],
                int(observation["degradation_parameter_seed"]),
                canvas_shape=(self.canvas_size, self.canvas_size), crop_yx=(y0, x0),
                hidden_parameters=hidden,
            )
            optical_rows.append(layers.shape_optical + layers.texture_optical)
            support_rows.append(REPLAY.boundary_support_from_metadata(mask_u8, observation["degradation"]))
            branch_rows["local_contrast_component"].append(layers.local_contrast_target)
            branch_rows["boundary_component"].append(layers.boundary_target)
            branch_rows["texture_component"].append(layers.texture_target)
            branch_rows["local_contrast_clean"].append(layers.shape_prefade + layers.texture_prefade)
            branch_rows["local_contrast_optical"].append(layers.shape_optical + layers.texture_optical)
            branch_rows["boundary_clean"].append(layers.shape_clean)
            branch_rows["boundary_optical"].append(layers.shape_prefade)
            branch_rows["texture_clean"].append(layers.texture_clean)
            branch_rows["texture_optical"].append(layers.texture_prefade)
            source_rows.append(source_u8)
            noise_free_rows.append(noise_free_u8)
            target_rows.append(target_u8)
            mask_rows.append(mask_u8)
            motions.append((dx, dy))
            identities.append(observation["degradation_family"] == "identity_and_near_identity")
            recoverability.append(float(observation["detail_recoverability"]))
            position = observation["degradation"].get("exposure_path_position")
            exposure_positions.append(-1.0 if position is None else float(position))

        source_tensor = _as_float(source_rows)
        noise_free_tensor = _as_float(noise_free_rows)
        target_tensor = _as_float(target_rows)
        mask_tensor = _as_float(mask_rows)
        optical_tensor = _as_layer(optical_rows)
        support_tensor = _as_layer(support_rows)
        layer_tensors = {name: _as_layer(rows) for name, rows in branch_rows.items()}
        views = TARGETS.build_counterfactual_views(
            target_tensor, noise_free_tensor, source_tensor,
            boundary_support=support_tensor, optical_source=optical_tensor, **layer_tensors,
        )
        def pack_need(view: Any) -> torch.Tensor:
            return torch.cat([
                view.need_radiometry, view.need_noise, view.need_local_contrast,
                view.need_boundary, view.need_texture,
            ], dim=1)

        def pack_evidence(view: Any) -> torch.Tensor:
            return torch.cat([
                view.local_contrast_evidence, view.boundary_evidence,
                view.texture_recoverability,
            ], dim=1)

        need_truth_s = pack_need(views["S_noisy"])
        need_truth_t = pack_need(views["T_clear"])
        need_truth_b = pack_need(views["B_noise_free"])
        evidence_truth_s = pack_evidence(views["S_noisy"])
        evidence_truth_t = pack_evidence(views["T_clear"])
        evidence_truth_b = pack_evidence(views["B_noise_free"])

        def applied(view: Any, name: str) -> torch.Tensor:
            return getattr(view, f"{name}_effective")

        # These are the corrections that are actually allowed to reach the
        # output.  R97 supervises them directly for noisy S, noise-free B and
        # exact-clear T; it never trains an ungated value and attenuates it a
        # second time at inference.
        direct_targets = {}
        for suffix, view in (
            ("s", views["S_noisy"]),
            ("b", views["B_noise_free"]),
            ("t", views["T_clear"]),
        ):
            for name in ("radiometry", "nuisance", "local_contrast", "boundary", "texture"):
                direct_targets[f"{name}_applied_target_{suffix}"] = applied(view, name)
        texture = record["texture"]
        foreground_mean = float(texture["foreground_mean"])
        background_mean = float(texture["background_mean"])
        transition_fraction = float(texture["physical_boundary_intensity_fraction"])
        boundary_level = (1.0 - transition_fraction) * background_mean + transition_fraction * foreground_mean
        return {
            "source": source_tensor,
            "noise_free_source": noise_free_tensor,
            "target": target_tensor,
            "mask": mask_tensor,
            "optical_source": optical_tensor,
            "boundary_support_truth": support_tensor,
            **{f"layer_{name}": tensor for name, tensor in layer_tensors.items()},
            "supervised_target": views["S_noisy"].target,
            "supervised_target_s": views["S_noisy"].target,
            "supervised_target_b": views["B_noise_free"].target,
            "supervised_target_t": views["T_clear"].target,
            # Keep the short aliases for reconstruction validation while also
            # exposing every same-scene counterfactual explicitly.  Training
            # can now learn what changes between S, B and T instead of being
            # dominated by a separate all-zero clear-image penalty.
            "need_truth": need_truth_s,
            "evidence_truth": evidence_truth_s,
            "need_truth_s": need_truth_s,
            "need_truth_t": need_truth_t,
            "need_truth_b": need_truth_b,
            "evidence_truth_s": evidence_truth_s,
            "evidence_truth_t": evidence_truth_t,
            "evidence_truth_b": evidence_truth_b,
            "radiometry_target": views["S_noisy"].radiometry_component,
            "nuisance_target": views["S_noisy"].nuisance_component,
            "local_contrast_target": views["S_noisy"].local_contrast_component,
            "boundary_target": views["S_noisy"].boundary_component,
            "texture_target": views["S_noisy"].texture_component,
            **direct_targets,
            "motion": torch.tensor(motions, dtype=torch.float32),
            "identity": torch.tensor(identities, dtype=torch.bool),
            "pair_kind": torch.tensor(pair_kind, dtype=torch.int64),
            "observation_indices": torch.tensor(observation_indices, dtype=torch.int64),
            "detail_recoverability": torch.tensor(recoverability, dtype=torch.float32),
            "exposure_path_position": torch.tensor(exposure_positions, dtype=torch.float32),
            "boundary_level": torch.tensor(boundary_level, dtype=torch.float32),
            "polarity": torch.tensor(1.0 if bool(texture["bright_foreground"]) else -1.0),
            "crop_foreground_fraction": torch.tensor(foreground_fraction, dtype=torch.float32),
            "crop_boundary_pixels": torch.tensor(boundary_pixels, dtype=torch.int64),
            "role": str(record["role"]),
            "scene_id": str(record["scene_id"]),
        }


class RoleBalancedBatchSampler(Sampler[list[int]]):
    """Role-balanced scene groups; trainer microbatches the paired views."""

    def __init__(self, dataset: R97SceneDataset, batch_size: int, seed: int):
        self.batch_size = int(batch_size)
        self.seed = int(seed)
        groups: dict[tuple[int, str], list[int]] = defaultdict(list)
        for index in range(len(dataset)):
            groups[(dataset.view_count_at(index), dataset.role_at(index))].append(index)
        self.groups = groups
        self.local_batch_sizes = {key: self.batch_size for key in groups}
        self.batches_per_group = {
            key: max(1, math.ceil(len(indices) / self.local_batch_sizes[key]))
            for key, indices in groups.items()
        }

    def __len__(self) -> int:
        return sum(self.batches_per_group.values())

    def __iter__(self):
        batches: list[list[int]] = []
        for key in sorted(self.groups):
            indices = self.groups[key]
            local_batch = self.local_batch_sizes[key]
            for start in range(0, len(indices), local_batch):
                batch = indices[start:start + local_batch]
                if len(batch) < local_batch:
                    needed = local_batch - len(batch)
                    batch.extend(indices[:needed])
                batches.append(batch)
        if batches:
            offset = self.seed % len(batches)
            batches = batches[offset:] + batches[:offset]
        return iter(batches)


class HomogeneousValidationSampler(Sampler[list[int]]):
    def __init__(self, dataset: R97SceneDataset, batch_size: int = 1):
        groups: dict[int, list[int]] = defaultdict(list)
        for index in range(len(dataset)):
            groups[dataset.view_count_at(index)].append(index)
        self.batches = [
            indices[start:start + batch_size]
            for view_count in sorted(groups)
            for indices in (groups[view_count],)
            for start in range(0, len(indices), batch_size)
        ]

    def __len__(self) -> int:
        return len(self.batches)

    def __iter__(self):
        return iter(self.batches)


class RoleBalancedValidationSampler(Sampler[list[int]]):
    """Small deterministic validation panel with equal role representation."""

    def __init__(self, dataset: R97SceneDataset, per_role: int = 8):
        groups: dict[str, list[int]] = defaultdict(list)
        for index in range(len(dataset)):
            groups[dataset.role_at(index)].append(index)
        selected: dict[str, list[int]] = {}
        for role, indices in sorted(groups.items()):
            count = min(max(1, int(per_role)), len(indices))
            positions = np.linspace(0, len(indices) - 1, num=count, dtype=np.int64)
            selected[role] = [indices[int(position)] for position in positions]
        self.batches = []
        for offset in range(max((len(indices) for indices in selected.values()), default=0)):
            for role in sorted(selected):
                if offset < len(selected[role]):
                    self.batches.append([selected[role][offset]])

    def __len__(self) -> int:
        return len(self.batches)

    def __iter__(self):
        return iter(self.batches)


