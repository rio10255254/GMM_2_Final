"""Focused contract tests for the split-profile locked ACM runner."""
from __future__ import annotations

import unittest

from validation.run_split_profile_locked_acm import (
    SUITE_SPECS,
    canonical_json_sha256,
    expected_counts,
    read_json,
    selected_records,
    validate_full_manifest,
    validate_method_name,
)


class SplitProfileLockedAcmRunnerTests(unittest.TestCase):
    def test_sealed_manifests_match_locked_contracts(self) -> None:
        for suite, spec in SUITE_SPECS.items():
            with self.subTest(suite=suite):
                manifest = read_json(spec["manifest"])
                template = read_json(spec["template"])
                records = validate_full_manifest(suite, manifest, template)
                self.assertEqual(len(records), int(template["dataset"]["total_images"]))
                self.assertEqual(len(records), 100)

    def test_smoke_changes_only_dataset_scope_not_acm(self) -> None:
        suite = "R73"
        spec = SUITE_SPECS[suite]
        manifest = read_json(spec["manifest"])
        template = read_json(spec["template"])
        records = validate_full_manifest(suite, manifest, template)
        primary, inference, config = selected_records(records, template, smoke=True)
        self.assertEqual(len(primary), 1)
        self.assertEqual(len(inference), 3)
        self.assertEqual(config["acm"], template["acm"])
        self.assertEqual(
            canonical_json_sha256(config["acm"]), canonical_json_sha256(template["acm"])
        )
        self.assertEqual(
            expected_counts(config, method_count=2),
            {"primary_rows": 4, "truth_rows": 1, "sensitivity_rows": 18},
        )

    def test_full_selection_retains_all_locked_records(self) -> None:
        suite = "R74"
        spec = SUITE_SPECS[suite]
        manifest = read_json(spec["manifest"])
        template = read_json(spec["template"])
        records = validate_full_manifest(suite, manifest, template)
        primary, inference, config = selected_records(records, template, smoke=False)
        self.assertEqual(primary, records)
        self.assertEqual(inference, records)
        self.assertEqual(config, template)
        self.assertEqual(
            expected_counts(config, method_count=2),
            {"primary_rows": 400, "truth_rows": 100, "sensitivity_rows": 90},
        )

    def test_method_name_is_fail_closed(self) -> None:
        validate_method_name("R114SplitE028")
        for invalid in ("Raw", "TruthACM", "R114-E028", "114Split"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_method_name(invalid)


if __name__ == "__main__":
    unittest.main()
