import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_checks_node', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


class ChecksNodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        (self.source / 'package.json').write_text(json.dumps({'engines': {'node': '26.12.1'}}))
        patch.object(customize, 'SOURCE', self.source).start()
        self.addCleanup(patch.stopall)

    def test_the_pin_comes_from_engines_without_a_server_vite_config(self):
        self.assertEqual(customize.sea_node_version(self.source), '26.12.1')

    def test_env_puts_the_pinned_node_in_front(self):
        with patch.object(customize, 'exact_node', return_value=Path('/cache/node-v26.12.1/bin')) as exact:
            env = customize.upstream_node_env({'PATH': '/usr/bin'}, io.StringIO())
        exact.assert_called_once()
        self.assertEqual(exact.call_args.args[0], '26.12.1')
        self.assertEqual(env['PATH'].split(os.pathsep), ['/cache/node-v26.12.1/bin', '/usr/bin'])
        self.assertEqual(env['VP_NODE_VERSION'], '26.12.1')

    def test_an_unfetchable_node_stops_instead_of_using_the_system_node(self):
        with patch.object(customize, 'exact_node', side_effect=OSError('offline')):
            with self.assertRaises(customize.Stop) as stop:
                customize.upstream_node_env({'PATH': '/usr/bin'}, io.StringIO())
        self.assertIn('26.12.1', str(stop.exception))
        self.assertIn('not fall back', str(stop.exception))

    def test_no_pin_stops(self):
        (self.source / 'package.json').write_text('{}')
        with self.assertRaises(customize.Stop):
            customize.upstream_node_env({}, io.StringIO())

    def test_checks_run_every_step_on_the_pinned_node(self):
        seen = []
        patch.object(customize, 'checks_stamped', lambda target: False).start()
        patch.object(customize, 'WITH_IOS', False).start()
        patch.object(customize, 'CACHE', self.source / 'cache').start()
        patch.object(customize, 'check_spec', lambda: {'tests': ['a.test.ts'], 'typecheck': ['apps/x']}).start()
        patch.object(customize, 'typechecker', lambda log=None: ['tsc']).start()
        patch.object(customize, 'git', lambda *a, **k: '').start()
        patch.object(customize, 'git_dir', lambda: self.source).start()
        patch.object(customize, 'step', lambda *a, **k: None).start()
        patch.object(customize, 'say', lambda *a, **k: None).start()
        patch.object(customize, 'exact_node', lambda version, log: Path('/cache/node-v26.12.1/bin')).start()
        (self.source / 'a.test.ts').write_text('')
        patch.object(customize, 'run_test_step',
                     lambda args, cwd, env, log, tmp, target: (seen.append(env) or True, [])).start()
        patch.object(customize, 'run_bounded',
                     lambda args, env, log, timeout, **k: (seen.append(env) or 0, '')).start()
        customize.checks({'PATH': '/usr/bin'}, io.StringIO(), 'base', force=True)
        self.assertEqual(len(seen), 2)
        for env in seen:
            self.assertTrue(env['PATH'].startswith('/cache/node-v26.12.1/bin'))
            self.assertEqual(env['VP_NODE_VERSION'], '26.12.1')
