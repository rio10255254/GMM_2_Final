"""Safety checks for export/restore of irreplaceable research artifacts."""
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('research_recovery', Path(__file__).parents[1] / 'research_recovery.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecoverySafetyTests(unittest.TestCase):
    def test_archive_path_escape_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('valid.txt', 'first')
                z.writestr('../outside.txt', 'bad')
            destination = base / 'restore'
            with self.assertRaises(ValueError):
                MODULE.restore_zip(archive, destination)
            self.assertFalse(destination.exists())
            self.assertFalse((base / 'outside.txt').exists())

    def test_restore_will_not_overwrite_existing_research(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destination = base / 'restore'
            destination.mkdir()
            old = destination / 'important.csv'
            old.write_text('original', encoding='utf-8')
            archive = base / 'new.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('important.csv', 'replacement')
            with self.assertRaises(FileExistsError):
                MODULE.restore_zip(archive, destination)
            self.assertEqual(old.read_text(encoding='utf-8'), 'original')

    def test_missing_review_and_inside_project_exports_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'project'
            root.mkdir()
            selection = base / 'selection.json'
            selection.write_text(json.dumps({'reviewed': False, 'files': []}), encoding='utf-8')
            with self.assertRaises(ValueError):
                MODULE.copy_selected(root, selection, base / 'export')
            with self.assertRaises(ValueError):
                MODULE.copy_selected(root, selection, root / 'export')

    def test_changed_measurement_is_detected_and_original_receipt_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'measure.csv').write_bytes(b'1,2,3')
            manifest = base / 'manifest.json'
            manifest.write_text(json.dumps({'files': [{'path': 'measure.csv', 'bytes': 5,
                'sha256': hashlib.sha256(b'1,2,4').hexdigest()}]}), encoding='utf-8')
            report = base / 'check.json'
            self.assertEqual(MODULE.verify_files(base, manifest, report), 1)
            receipt = report.read_bytes()
            with self.assertRaises(FileExistsError):
                MODULE.verify_files(base, manifest, report)
            self.assertEqual(report.read_bytes(), receipt)

    def test_downloaded_compressed_catalog_verifies_the_exact_saved_measurement(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            data = b'scan,error_nm\n1,-2.75\n'
            (base / 'measure.csv').write_bytes(data)
            manifest = base / 'REPOSITORY_FILES.json.gz'
            with gzip.open(manifest, 'wt', encoding='utf-8') as stream:
                json.dump({'files': [{'path': 'measure.csv', 'bytes': len(data),
                                      'sha256': hashlib.sha256(data).hexdigest()}]}, stream)
            self.assertEqual(MODULE.verify_files(base, manifest, base / 'verified.json'), 0)
            self.assertEqual((base / 'measure.csv').read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
