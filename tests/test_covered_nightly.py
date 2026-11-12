import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_covered', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

OLD = '0.1.10-nightly.20261112.4564'
NEW = '0.1.10-nightly.20261112.4580'


class CoveredNightlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.file = self.folder / customize.COVERED_NIGHTLY

    def test_a_nightly_version_has_a_comparable_key(self):
        self.assertEqual(customize.nightly_key(NEW), (0, 1, 10, 20261112, 4580))
        self.assertLess(customize.nightly_key('0.1.9-nightly.20261113.9'), customize.nightly_key(OLD))
        self.assertLess(customize.nightly_key(OLD), customize.nightly_key(NEW))
        for text in (None, '', '1.2.3', '40526f96f6ae', '<html>', NEW + '-x'):
            self.assertIsNone(customize.nightly_key(text), text)

    def test_the_file_follows_the_newest_nightly_and_never_goes_back(self):
        customize.write_covered_nightly(OLD, self.folder)
        self.assertEqual(self.file.read_text(), OLD + '\n')
        customize.write_covered_nightly(NEW, self.folder)
        self.assertEqual(self.file.read_text(), NEW + '\n')
        customize.write_covered_nightly(OLD, self.folder)
        self.assertEqual(self.file.read_text(), NEW + '\n')

    def test_a_version_that_is_not_a_nightly_leaves_the_file_alone(self):
        customize.write_covered_nightly('40526f96f6ae', self.folder)
        customize.write_covered_nightly(None, self.folder)
        self.assertFalse(self.file.exists())
        customize.write_covered_nightly(NEW, self.folder)
        customize.write_covered_nightly('40526f96f6ae', self.folder)
        self.assertEqual(self.file.read_text(), NEW + '\n')

    def test_a_garbled_file_is_replaced(self):
        self.file.write_text('<html>\n')
        customize.write_covered_nightly(OLD, self.folder)
        self.assertEqual(self.file.read_text(), OLD + '\n')

    def test_export_writes_it_in_the_repo_or_under_a_dry_run_root(self):
        repo, dry = self.folder / 'repo', self.folder / 'dry'
        repo.mkdir()
        with patch.object(customize, 'REPO', repo), patch.object(customize, 'PORT', repo / 'patches-port'), \
                patch.object(customize, 'git', lambda *args, **kwargs: ''), \
                patch.object(customize, 'patches', lambda: []), \
                patch.object(customize, 'own_layers', lambda: [repo / 'patches-tt']), \
                patch.object(customize, 'layer_patches', lambda folder: []):
            customize.export_patches('a' * 40, version=NEW)
            customize.export_patches('b' * 40, root=dry, version=OLD)
            customize.export_patches('c' * 40)
        self.assertEqual((repo / customize.COVERED_NIGHTLY).read_text(), NEW + '\n')
        self.assertEqual((dry / customize.COVERED_NIGHTLY).read_text(), OLD + '\n')

    def test_the_file_is_a_port_file_so_it_never_blocks_the_standing_grant(self):
        self.assertTrue(customize.is_port_file('covered-nightly.txt'))
        self.assertFalse(customize.is_port_file('sub/covered-nightly.txt'))
        repo = self.folder / 'repo'
        repo.mkdir()

        def git(*args):
            subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=repo, check=True,
                           capture_output=True)
        git('init', '-q')
        (repo / 'README.md').write_text('x')
        git('add', '.')
        git('commit', '-qm', 'init')
        (repo / customize.COVERED_NIGHTLY).write_text(NEW + '\n')
        with patch.object(customize, 'REPO', repo):
            self.assertEqual(customize.port_changes(), ([customize.COVERED_NIGHTLY], []))
            git('add', '.')
            git('commit', '-qm', 'covered')
            (repo / customize.COVERED_NIGHTLY).write_text(OLD + '\n')
            self.assertEqual(customize.port_changes(), ([customize.COVERED_NIGHTLY], []))


if __name__ == '__main__':
    unittest.main()
