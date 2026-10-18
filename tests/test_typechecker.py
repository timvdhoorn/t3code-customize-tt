import importlib.machinery
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_typechecker', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


class TypecheckerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        self.bin = self.source / 'node_modules' / '.bin'
        self.bin.mkdir(parents=True)
        (self.bin / 'tsc').write_text('')
        patcher = patch.object(customize, 'SOURCE', self.source)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_tsc_rs_when_installed(self):
        (self.bin / 'tsc-rs').write_text('')
        log = io.StringIO()
        self.assertEqual(customize.typechecker(log), 'tsc-rs')
        self.assertEqual(log.getvalue(), '')

    def test_windows_shim_counts(self):
        (self.bin / 'tsc-rs.cmd').write_text('')
        self.assertEqual(customize.typechecker(), 'tsc-rs')

    def test_falls_back_to_tsc_and_logs_it(self):
        log = io.StringIO()
        self.assertEqual(customize.typechecker(log), 'tsc')
        self.assertIn('typechecking with tsc', log.getvalue())


if __name__ == '__main__':
    unittest.main()
