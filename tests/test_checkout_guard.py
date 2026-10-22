import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_guard', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

ROUTE_TREE = 'apps/web/src/routeTree.gen.ts'
UNIWIND = 'apps/mobile/uniwind-types.d.ts'


class RestoreGeneratedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name)
        run = lambda *a: subprocess.run(['git', *a], cwd=self.source, check=True, capture_output=True)
        run('init', '-q')
        (self.source / 'apps/web/src').mkdir(parents=True)
        (self.source / ROUTE_TREE).write_text('routes\n')
        (self.source / 'apps/mobile').mkdir(parents=True)
        (self.source / UNIWIND).write_text('types\n')
        (self.source / 'other.ts').write_text('code\n')
        run('add', '.')
        run('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base')
        patcher = patch.object(customize, 'SOURCE', self.source)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_build_rewrite_of_route_tree_is_undone(self):
        (self.source / ROUTE_TREE).write_text('// generated header\nroutes\n')
        customize.restore_generated()
        self.assertEqual((self.source / ROUTE_TREE).read_text(), 'routes\n')

    def test_other_edits_keep_everything_for_the_guard(self):
        (self.source / ROUTE_TREE).write_text('// generated header\nroutes\n')
        (self.source / 'other.ts').write_text('a port in progress\n')
        customize.restore_generated()
        self.assertEqual((self.source / ROUTE_TREE).read_text(), '// generated header\nroutes\n')
        self.assertEqual((self.source / 'other.ts').read_text(), 'a port in progress\n')

    def test_ios_rewrite_of_uniwind_types_is_undone(self):
        (self.source / ROUTE_TREE).write_text('// generated header\nroutes\n')
        (self.source / UNIWIND).write_text('regenerated types\n')
        customize.restore_generated()
        self.assertEqual((self.source / UNIWIND).read_text(), 'types\n')
        self.assertEqual((self.source / ROUTE_TREE).read_text(), 'routes\n')

    def test_a_build_undoes_every_tracked_file_it_rewrote(self):
        (self.source / 'untracked.log').write_text('output\n')
        with customize.build_rewrites_discarded():
            (self.source / 'other.ts').write_text('rewritten by the build\n')
            (self.source / UNIWIND).write_text('regenerated types\n')
        self.assertEqual((self.source / 'other.ts').read_text(), 'code\n')
        self.assertEqual((self.source / UNIWIND).read_text(), 'types\n')
        self.assertTrue((self.source / 'untracked.log').exists())

    def test_a_failed_build_step_still_undoes_its_rewrites(self):
        with self.assertRaises(customize.Stop):
            with customize.build_rewrites_discarded():
                (self.source / 'other.ts').write_text('half written\n')
                raise customize.Stop('build failed')
        self.assertEqual((self.source / 'other.ts').read_text(), 'code\n')


class UncommittedChangesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.origin = Path(self.tmp.name) / 'origin'
        self.origin.mkdir()
        run = lambda *a: subprocess.run(['git', *a], cwd=self.origin, check=True, capture_output=True)
        run('init', '-q')
        (self.origin / 'code.ts').write_text('code\n')
        run('add', '.')
        run('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base')

    def use(self, source):
        patcher = patch.object(customize, 'SOURCE', source)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_fresh_no_checkout_clone_is_clean(self):
        source = Path(self.tmp.name) / 'clone'
        subprocess.run(['git', 'clone', '-q', '--no-checkout', str(self.origin), str(source)],
                       check=True, capture_output=True)
        self.use(source)
        self.assertFalse(customize.uncommitted_changes())

    def test_an_edit_is_an_uncommitted_change(self):
        self.use(self.origin)
        self.assertFalse(customize.uncommitted_changes())
        (self.origin / 'code.ts').write_text('a port in progress\n')
        self.assertTrue(customize.uncommitted_changes())


if __name__ == '__main__':
    unittest.main()
