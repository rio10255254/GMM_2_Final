"""Original camera restoration must reject an unrelated ZIP or an occupied target."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

TOOLS=Path(__file__).parents[1]
sys.path.insert(0,str(TOOLS))
SPEC=importlib.util.spec_from_file_location('restore_pi_acquisition',TOOLS/'restore_pi_acquisition.py')
RESTORE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESTORE)


class OriginalCameraRestoreTests(unittest.TestCase):
    def test_existing_data_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/'originals';destination.mkdir()
            important=destination/'positions.csv';important.write_bytes(b'keep original bytes')
            with self.assertRaises(FileExistsError):
                RESTORE.restore(root/'none.zip',root/'none.json',destination)
            self.assertEqual(important.read_bytes(),b'keep original bytes')

    def test_wrong_acquisition_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'wrong.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('unrelated.bmp',b'unrelated')
            runs=[{'run':f'{i:06d}_XY_0','positions':{'sha256':'0'*64}} for i in range(30)]
            frames=[{'run':r['run'],'image':f'{i+1}.bmp','index':i,'source':{'sha256':'0'*64}}
                    for r in runs for i in range(31)]
            plan=root/'plan.json';plan.write_text(json.dumps({'runs':runs,'frames':frames}),encoding='utf-8')
            destination=root/'camera'
            with self.assertRaises(ValueError):RESTORE.restore(archive,plan,destination)
            self.assertFalse(destination.exists())


if __name__=='__main__':unittest.main()
