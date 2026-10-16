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


class RestoreGeneratedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name)
        run = lambda *a: subprocess.run(['git', *a], cwd=self.source, check=True, capture_output=True)
        run('init', '-q')
        (self.source / 'apps/web/src').mkdir(parents=True)
        (self.source / ROUTE_TREE).write_text('routes\n')
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


if __name__ == '__main__':
    unittest.main()
