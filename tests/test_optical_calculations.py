import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from optics_photonics.environments import bind
from optics_photonics.execution import run


@unittest.skipUnless(os.environ.get('OPTICS_SCIENCE_TESTS')=='1','Set OPTICS_SCIENCE_TESTS=1 in the scientific environment')
class ScienceTests(unittest.TestCase):
    def test_native_export_preserves_complex_fields_and_structure(self):
        import numpy as np
        from optics_photonics.native import export
        field = np.arange(24).reshape(2,3,4) * (1 + 2j)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = export({'field':field,'wavelength_m':np.float64(1.55e-6),'unit':'V/m'},'monitor',root)
            metadata = json.loads((root/result['metadata']).read_text())
            with np.load(root/result['data'],allow_pickle=False) as arrays:
                np.testing.assert_array_equal(arrays[metadata['field']['array']],field)
                self.assertEqual(arrays[metadata['wavelength_m']['array']].item(),1.55e-6)
            self.assertEqual(metadata['unit'],'V/m')
            from optics_photonics import data
            described = export({'E': data.quantity(field, 'electric field', unit='V/m', time_dependence='exp(-i omega t)')}, 'described', root)
            entry = json.loads((root/described['metadata']).read_text())['E']
            self.assertEqual((entry['shape'], entry['unit'], entry['time_dependence']), ([2,3,4], 'V/m', 'exp(-i omega t)'))

    def test_skills_have_readable_yaml_metadata(self):
        import yaml
        for path in (Path(__file__).resolve().parents[1]/'skills').glob('*/SKILL.md'):
            metadata=yaml.safe_load(path.read_text(encoding='utf-8').split('---',2)[1])
            self.assertEqual(metadata['name'],path.parent.name)
            self.assertIsInstance(metadata['description'],str)

    def test_native_program_keeps_full_api_and_result_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            bind('tmm',python=sys.executable,path=tmp)
            source='import tmm, numpy as np\nr=tmm.coh_tmm("s",[1,1.5],[np.inf,np.inf],0,550)\nnp.savetxt(OUTPUT_DIR/"R.csv",[r["R"]])\nRESULT={"R":float(r["R"]),"wavelength_nm":INPUTS["wavelength_nm"]}'
            a=run('tmm',{'source':source,'inputs':{'wavelength_nm':550}},path=tmp,timeout=30)['record']
            self.assertAlmostEqual(a['result']['R'],.04,places=12)
            self.assertIn('R.csv',a['files'])
            self.assertIn('tmm',a['environment']['versions'])
            self.assertIn('program.py',a['files'])


if __name__=='__main__':unittest.main()
