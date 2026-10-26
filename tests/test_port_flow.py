import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_port', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

IDENTITY = ['-c', 'user.name=t', '-c', 'user.email=t@t']


def git(cwd, *args):
    return subprocess.run(['git', *IDENTITY, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(cwd, files, message):
    for name, text in files.items():
        (Path(cwd) / name).write_text(text)
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', message)
    return git(cwd, 'rev-parse', 'HEAD')


class Sandbox(unittest.TestCase):
    """A T3 source with a base and a newer nightly, and a patch set of three layers made on the base:
    the shared patch and the patches-tt patch conflict with the nightly, the patches-ios one applies."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.recipe, self.cache = root / 'source', root / 'recipe', root / 'cache'
        for folder in (self.source, self.recipe, self.cache):
            folder.mkdir()
        git(self.source, 'init', '-q')
        self.base = commit(self.source, {'a.txt': '1\n', 'b.txt': '1\n', 'c.txt': '1\n'}, 'base')
        self.layers = {}
        for folder, name, text in (('patches', 'a.txt', '2\n'), ('patches-tt', 'b.txt', '2\n'),
                                   ('patches-ios', 'c.txt', '2\n')):
            commit(self.source, {name: text}, f'{folder} change')
            out = self.recipe / folder
            out.mkdir()
            git(self.source, 'format-patch', '-q', '-1', '-o', str(out))
        git(self.source, 'checkout', '-q', '--detach', self.base)
        self.nightly = commit(self.source, {'a.txt': 'x\n', 'b.txt': 'y\n'}, 'nightly')
        (self.recipe / 'patches' / 'base.txt').write_text(self.base + '\n')
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": []}\n')
        (root / 'machines.json').write_text('{"machines": []}\n')
        self.notes = []
        for name, value in (('SOURCE', self.source), ('CACHE', self.cache), ('WITH_IOS', True),
                            ('DATA', root / 'data'), ('PORTS', root / 'data/ports.json'),
                            ('HANDOFFS', root / 'data/handoffs.json'), ('MACHINES', root / 'machines.json'),
                            ('notify', lambda title, message: self.notes.append(message)),
                            ('fork_repo', lambda: None)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(customize.use_recipe, customize.REPO)
        customize.use_recipe(self.recipe)
        self.log = (root / 'log').open('w+')
        self.addCleanup(self.log.close)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('T3CODE_CUSTOMIZE_LOCK_HELD', None)

    def clean(self):
        return not customize.rebase_in_progress() and not git(self.source, 'status', '--porcelain', '--untracked-files=no')

    def quiet(self, function, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = function(*args, **kwargs)
        return result, out.getvalue()

    def prepare(self, **kwargs):
        customize.choose_shared(self.log)
        return customize.prepare(self.nightly, self.log, version='n2', **kwargs)

    def resolve(self, name, text):
        (self.source / name).write_text(text)
        git(self.source, 'add', name)

    def cont(self):
        return self.quiet(customize.cmd_continue, argparse.Namespace(target=None, ios=False))[1]


class StageLoopTest(Sandbox):
    def test_continue_walks_every_stage_until_all_patches_are_applied(self):
        with self.assertRaises(customize.NeedsFix) as stop:
            self.prepare()
        self.assertIn('The shared patches conflict', str(stop.exception))
        self.assertIn('t3code-customize continue', str(stop.exception))
        self.resolve('a.txt', '2\n')
        with self.assertRaises(customize.NeedsFix) as stop:
            self.cont()
        self.assertIn('patches-tt/ conflict', str(stop.exception))
        self.assertIn('b.txt', str(stop.exception))
        self.resolve('b.txt', '2\n')
        self.assertIn('All patches applied.', self.cont())
        self.assertEqual(git(self.source, 'rev-list', '--count', self.nightly + '..HEAD'), '3')
        self.assertEqual((self.source / 'c.txt').read_text(), '2\n')
        self.assertFalse(customize.rebase_in_progress())

    def test_continue_refuses_while_files_are_still_conflicted(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare()
        with self.assertRaises(customize.NeedsFix) as stop:
            self.cont()
        self.assertIn('Still conflicted', str(stop.exception))
        self.assertTrue(customize.rebase_in_progress())

    def test_the_marker_names_the_nightly_and_the_layers_for_continue_and_checks(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        marker = customize.run_marker()
        self.assertEqual((marker['target'], marker['version'], marker['ios'], marker['unattended']),
                         (self.nightly, 'n2', True, True))


class StoppedCheckoutTest(Sandbox):
    def unattended_stop(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        customize.mark_unattended_stop()
        self.assertTrue(customize.rebase_in_progress())

    def assert_protected(self):
        with self.assertRaises(customize.Stop) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertNotIsInstance(stop.exception, customize.NeedsFix)
        self.assertIn('stopped rebase or git am', str(stop.exception))
        self.assertTrue(customize.rebase_in_progress())

    def test_an_unattended_run_aborts_the_stop_an_unattended_run_left(self):
        self.unattended_stop()
        with self.assertRaises(customize.NeedsFix) as stop:
            self.quiet(self.prepare, unattended=True)
        # It started over: the stop it reports is a fresh one, not the guard.
        self.assertIn('The shared patches conflict', str(stop.exception))

    def test_continue_claims_the_stop_before_the_next_unattended_run(self):
        self.unattended_stop()
        self.resolve('a.txt', '2\n')
        with self.assertRaises(customize.NeedsFix):
            self.cont()  # on to patches-tt/, which conflicts too
        self.assertFalse(customize.run_marker()['unattended'])
        self.assert_protected()
        self.assertEqual(git(self.source, 'rev-list', '--count', self.nightly + '..HEAD'), '1')

    def test_checks_and_resume_claim_the_stop(self):
        self.unattended_stop()
        with self.assertRaises(customize.NeedsFix):
            self.quiet(customize.cmd_checks, argparse.Namespace(target=None, ios=False, force=False))
        self.assertFalse(customize.run_marker()['unattended'])
        self.assert_protected()
        customize.update_run_marker(unattended=True)
        args = argparse.Namespace(resume=True, skip_checks=True, fix=None, background=False)
        with self.assertRaises(customize.NeedsFix):
            self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertFalse(customize.run_marker()['unattended'])
        self.assert_protected()

    def test_work_without_continue_after_the_stop_stays_protected(self):
        # The other order: someone resolves files (staged or not) but has not run continue yet.
        self.unattended_stop()
        self.resolve('a.txt', '2\n')
        self.assertTrue(customize.run_marker()['unattended'])
        self.assert_protected()
        self.assertEqual(git(self.source, 'diff', '--cached', '--name-only'), 'a.txt')

    def test_the_run_holding_the_lock_does_not_claim_its_own_stop(self):
        self.unattended_stop()
        os.environ['T3CODE_CUSTOMIZE_LOCK_HELD'] = '1'
        customize.claim_checkout()
        self.assertTrue(customize.run_marker()['unattended'])

    def test_edits_an_unattended_run_left_without_a_rebase_are_cleaned_too(self):
        self.unattended_stop()
        self.resolve('a.txt', '2\n')
        with self.assertRaises(customize.NeedsFix):
            self.quiet(customize.cmd_continue, argparse.Namespace(target=None, ios=False))
        # Pretend an agent session (holding the lock) left uncommitted edits and no rebase.
        self.resolve('b.txt', '2\n')
        self.cont()
        (self.source / 'a.txt').write_text('half done\n')
        customize.update_run_marker(unattended=True)
        customize.mark_unattended_stop()
        self.assertFalse(customize.rebase_in_progress())
        with self.assertRaises(customize.NeedsFix) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertIn('The shared patches conflict', str(stop.exception))

    def test_a_stop_a_person_or_agent_started_stays_protected(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=False)
        customize.mark_unattended_stop()
        self.assert_protected()

    def test_a_stop_without_a_marker_stays_protected(self):
        self.unattended_stop()
        (customize.git_dir() / customize.RUN_MARK).unlink()
        self.assert_protected()


class ChecksStampTest(Sandbox):
    def setUp(self):
        super().setUp()
        git(self.source, 'checkout', '-q', '--detach', self.base)

    def test_checks_that_passed_on_this_commit_are_skipped(self):
        customize.save(customize.git_dir() / customize.CHECKS_STAMP, customize.checks_stamp(self.base))
        with patch.object(customize, 'run_bounded', side_effect=AssertionError('ran a check')):
            _, out = self.quiet(customize.checks, {}, self.log, self.base)
        self.assertIn('already passed on this commit', out)

    def test_a_new_commit_nightly_check_list_or_recipe_runs_them_again(self):
        stamp = customize.git_dir() / customize.CHECKS_STAMP
        customize.save(stamp, customize.checks_stamp(self.base))
        self.assertTrue(customize.checks_stamped(self.base))
        self.assertFalse(customize.checks_stamped(self.nightly))
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": ["x"]}\n')
        self.assertFalse(customize.checks_stamped(self.base))
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": []}\n')
        self.assertTrue(customize.checks_stamped(self.base))
        with patch.object(customize, 'recipe_hash', return_value='another script'):
            self.assertFalse(customize.checks_stamped(self.base))
        git(self.source, 'checkout', '-q', '--detach', self.nightly)
        self.assertFalse(customize.checks_stamped(self.base))

    def test_passing_checks_write_the_stamp_and_force_ignores_it(self):
        calls = []

        def fake(args, env, log, timeout, cwd=None, merge=False):
            calls.append(args)
            return 0, ''
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": ["packages/x"]}\n')
        with patch.object(customize, 'run_bounded', fake):
            self.quiet(customize.checks, {}, self.log, self.base)
            self.assertTrue(customize.checks_stamped(self.base))
            self.assertEqual(customize.load(customize.git_dir() / customize.CHECKS_STAMP)['target'], self.base)
            self.quiet(customize.checks, {}, self.log, self.base, force=True)
        self.assertEqual(len(calls), 2)


# Stands in for `vp test run`: the full run fails slow.test.ts by a timeout and bad.test.ts for real;
# slow.test.ts alone passes when FAKE_RERUN is "pass".
FAKE_VP = '''#!{python}
import json, os, sys
args = sys.argv[1:]
files = [a for a in args if a.endswith('.test.ts')]
out = next((a.split('=', 1)[1] for a in args if a.startswith('--outputFile.json=')), None)
with open(os.environ['FAKE_CALLS'], 'a') as calls:
    calls.write(' '.join(files) + '\\n')
results = []
for name in files:
    if name == 'slow.test.ts' and (len(files) > 1 or os.environ['FAKE_RERUN'] != 'pass'):
        results.append(dict(name=os.path.join(os.getcwd(), name), status='failed', message='',
                            assertionResults=[dict(status='failed', failureMessages=['Error: Test timed out in 60000ms.'])]))
    elif name == 'bad.test.ts':
        results.append(dict(name=os.path.join(os.getcwd(), name), status='failed', message='',
                            assertionResults=[dict(status='failed', failureMessages=['AssertionError: expected 1 to be 2'])]))
    else:
        results.append(dict(name=os.path.join(os.getcwd(), name), status='passed', message='', assertionResults=[]))
if out:
    json.dump(dict(testResults=results), open(out, 'w'))
if os.environ.get('FAKE_UNHANDLED') and len(files) > 1:
    print('Vitest caught 1 unhandled error during the test run.')
    print('⎯⎯ Unhandled Rejection ⎯⎯')
    sys.exit(1)
sys.exit(1 if any(r['status'] == 'failed' for r in results) else 0)
'''


@unittest.skipIf(os.name == 'nt', 'the fake vp is a POSIX script')
class TimeoutRerunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        vp = self.root / 'bin' / 'vp'
        vp.write_text(FAKE_VP.format(python=sys.executable))
        vp.chmod(0o755)
        self.calls = self.root / 'calls'
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'],
                        FAKE_CALLS=str(self.calls))
        self.log = (self.root / 'log').open('w+')
        self.addCleanup(self.log.close)
        patcher = patch.object(customize, 'SOURCE', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def step(self, files, rerun):
        self.env['FAKE_RERUN'] = rerun
        with contextlib.redirect_stdout(io.StringIO()):
            return customize.run_test_step(['vp', 'test', 'run', *files], self.root, self.env, self.log, self.root)

    def test_a_file_that_only_timed_out_passes_when_it_passes_alone(self):
        self.assertEqual(self.step(['ok.test.ts', 'slow.test.ts'], 'pass'), (True, []))
        self.assertEqual(self.calls.read_text().splitlines(), ['ok.test.ts slow.test.ts', 'slow.test.ts'])
        self.log.seek(0)
        log = self.log.read()
        self.assertIn('slow.test.ts failed only by timeout', log)
        self.assertIn('slow.test.ts passed on its own', log)

    def test_an_unhandled_error_still_fails_after_the_timeouts_passed_alone(self):
        self.env['FAKE_UNHANDLED'] = '1'
        passed, failing = self.step(['ok.test.ts', 'slow.test.ts'], 'pass')
        self.assertFalse(passed)
        self.assertIn('unhandled error', failing[0])

    def test_an_unhandled_error_without_a_failed_file_fails(self):
        self.env['FAKE_UNHANDLED'] = '1'
        self.assertFalse(self.step(['ok.test.ts', 'ok2.test.ts'], 'pass')[0])

    def test_a_timeout_that_repeats_alone_counts_as_failed(self):
        self.assertEqual(self.step(['ok.test.ts', 'slow.test.ts'], 'fail'), (False, ['slow.test.ts (timeout)']))

    def test_a_real_failure_is_not_rerun(self):
        self.assertEqual(self.step(['bad.test.ts', 'slow.test.ts'], 'pass'), (False, ['bad.test.ts']))
        self.assertEqual(self.calls.read_text().splitlines(), ['bad.test.ts slow.test.ts', 'slow.test.ts'])

    def test_a_suite_error_is_not_a_timeout(self):
        report = {'testResults': [{'name': str(self.root / 'x.test.ts'), 'status': 'failed',
                                   'message': 'Failed to load module', 'assertionResults': []}]}
        self.assertEqual(customize.failed_test_files(report, Path('.')), {'x.test.ts': False})


class OlderNightlyTest(unittest.TestCase):
    """A repo whose patch set moved from nightly n1 to n2 and then got a feature; a source with both."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo, self.cache = root / 'repo', root / 'cache'
        self.repo.mkdir()
        (self.repo / 'patches').mkdir()
        (self.repo / 'patches-tt').mkdir()
        git(self.repo, 'init', '-q')
        (self.repo / 'patches' / 'base.txt').write_text('a' * 40 + '\n')
        self.first = commit(self.repo, {'patches-tt/0001-x.patch': 'v1\n'}, 'patches for n0')
        (self.repo / 'patches-port').mkdir()
        self.n1 = commit(self.repo, {'patches-port/base.txt': 'b' * 40 + '\n', 'patches-tt/0001-x.patch': 'v2\n'},
                         'port to n1')
        self.feature = commit(self.repo, {'patches-tt/0001-x.patch': 'v3\n'}, 'feature on n1')
        commit(self.repo, {'patches-port/base.txt': 'c' * 40 + '\n', 'patches-tt/0001-x.patch': 'v4\n'}, 'port to n2')
        # SOURCE is this repo too: the fake nightlies are unknown there, as they would be anywhere.
        for name, value in (('REPO', self.repo), ('CACHE', self.cache), ('SOURCE', self.repo)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_newest_patch_set_made_for_that_nightly_is_used(self):
        self.assertEqual(customize.recipe_for('b' * 40), self.feature)
        self.assertEqual(customize.recipe_for('a' * 40), self.first)
        folder = customize.extract_recipe(self.feature)
        self.assertEqual((folder / 'patches-tt/0001-x.patch').read_text(), 'v3\n')
        self.assertEqual((folder / 'patches-port/base.txt').read_text().strip(), 'b' * 40)

    def test_a_patch_set_without_a_layer_this_run_applies_is_skipped(self):
        (self.repo / 'patches-ios').mkdir()
        (self.repo / 'patches-ios' / '0001-y.patch').write_text('ios\n')
        with patch.object(customize, 'WITH_IOS', True), patch.object(customize, 'IOS_PATCHES', self.repo / 'patches-ios'):
            self.assertIsNone(customize.recipe_for('b' * 40))
            with_ios = commit(self.repo, {'patches-port/base.txt': 'b' * 40 + '\n'}, 'ios layer on n1')
            self.assertEqual(customize.recipe_for('b' * 40), with_ios)

    def test_the_base_follows_choose_shared(self):
        files = {'patches/base.txt': 'a' * 40, 'patches-port/base.txt': 'b' * 40}
        self.assertEqual(customize.effective_base(files.get, lambda old, new: True), 'b' * 40)
        # Upstream caught up past the port: patches-port/ is unused, so patches/ decides.
        self.assertEqual(customize.effective_base(files.get, lambda old, new: False), 'a' * 40)
        self.assertEqual(customize.effective_base({'patches/base.txt': 'a' * 40, 'patches-port/base.txt': 'a' * 40}.get), 'a' * 40)

    def test_no_patch_set_for_that_nightly_waits_for_the_app_update(self):
        self.assertIsNone(customize.recipe_for('d' * 40))
        with patch.object(customize, 'shared_base', return_value='c' * 40):
            with self.assertRaises(customize.Waiting) as waiting:
                customize.use_older_recipe('d' * 40, None)
        self.assertIn('waiting for the app update', str(waiting.exception))

    def test_waiting_exits_zero(self):
        self.assertTrue(issubclass(customize.Waiting, customize.Stop))
        self.assertFalse(issubclass(customize.Waiting, customize.NeedsFix))


class OlderNightlyApplyTest(Sandbox):
    def test_an_older_nightly_without_a_patch_set_never_touches_the_checkout(self):
        git(self.source, 'checkout', '-q', '--detach', self.nightly)
        (self.recipe / 'patches' / 'base.txt').write_text(self.nightly + '\n')
        args = argparse.Namespace(resume=False, skip_checks=True, fix=None, background=True)
        with patch.object(customize, 'recipe_for', return_value=None):
            with self.assertRaises(customize.Waiting):
                self.quiet(customize.apply_patches, args, self.base, 'n1', {}, self.log)
        self.assertFalse(customize.rebase_in_progress())
        self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), self.nightly)


class HandOffTest(Sandbox):
    MACHINES = {'machines': [{'name': 'mbp', 'hostname': 'MacBookPro', 'kind': 'mac', 'ssh': ['macbook-pro'], 'ios': True},
                             {'name': 'devbox1', 'hostname': 'devbox1', 'kind': 'server', 'ssh': ['devbox1'],
                              'fix': 'claude'}]}

    def setUp(self):
        super().setUp()
        machines = Path(self.tmp.name) / 'machines.json'
        machines.write_text(json.dumps(self.MACHINES))
        for name, value in (('MACHINES', machines), ('HANDOFFS', Path(self.tmp.name) / 'data/handoffs.json')):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.started = []
        patch.object(customize, 'this_machine', lambda machines: machines[0]).start()
        patch.object(customize, 'ssh_target', lambda machine: machine['ssh'][0]).start()
        patch.object(customize, 'notify', lambda title, message: self.started.append(('notify', message))).start()
        patch.object(customize, 'remote', self.remote).start()
        self.addCleanup(patch.stopall)

    def remote(self, alias, command, **kwargs):
        self.started.append((alias, command))
        return subprocess.CompletedProcess([], 0, '', '')

    def test_the_porter_command_ports_that_nightly_detached_and_once(self):
        porter = customize.porter_machine()
        self.assertEqual(porter['name'], 'devbox1')
        self.assertEqual(customize.port_command(porter, 'f' * 40, 'n2'),
                         ['port', '--commit', 'f' * 40, '--version', 'n2', '--fix', 'claude', '--background',
                          '--wait-lock', '180'])
        line = customize.remote_port_line(porter, 'f' * 40, 'n2', 'Devops/Personal/t3code-customize-tt')
        self.assertIn('systemd-run --user --collect --unit=t3code-customize-port-ffffffffffff', line)
        self.assertIn('python3 "$HOME"/Devops/Personal/t3code-customize-tt/t3code-customize port --commit', line)
        self.assertIn('nohup', line)

    def run_line(self, systemd):
        """Run the remote line with a fake systemd-run and a fake tool that records that it started."""
        root = Path(self.tmp.name)
        (root / 'bin').mkdir(exist_ok=True)
        (root / 'repo').mkdir(exist_ok=True)
        started = root / 'started'
        (root / 'repo' / 't3code-customize').write_text(f'open({str(started)!r}, "a").write("tool\\n")\n')
        fake = root / 'bin' / 'systemd-run'
        fake.write_text('#!/bin/sh\n' + systemd + '\n')
        fake.chmod(0o755)
        line = customize.remote_port_line(customize.porter_machine(), 'f' * 40, 'n2', str(root / 'repo'))
        env = dict(os.environ, HOME=str(root), PATH=f'{root / "bin"}:{os.environ["PATH"]}')
        out = subprocess.run(['sh', '-c', line + '; wait'], env=env, capture_output=True, text=True, timeout=30)
        return out.stdout, started.exists()

    @unittest.skipIf(os.name == 'nt', 'POSIX shell')
    def test_systemd_run_failing_otherwise_falls_back_to_nohup(self):
        out, started = self.run_line('echo "Failed to connect to bus: No medium found" >&2; exit 1')
        self.assertIn('systemd-run failed', out)
        self.assertIn('started with nohup', out)
        self.assertTrue(started)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell')
    def test_a_port_unit_that_runs_already_is_left_alone(self):
        out, started = self.run_line('echo "Failed to start transient service unit: Unit t.service was already loaded" >&2; exit 1')
        self.assertIn('already running', out)
        self.assertFalse(started)

    def test_a_machine_without_fix_hands_the_port_over_and_stays_clean(self):
        args = argparse.Namespace(resume=False, skip_checks=True, fix=None, background=True)
        with patch.object(customize, 'interactive', lambda: False):
            with self.assertRaises(customize.PortHandedOff) as stop:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertIn('Port running on devbox1', str(stop.exception))
        self.assertFalse(customize.rebase_in_progress())
        self.assertEqual(git(self.source, 'status', '--porcelain', '--untracked-files=no'), '')
        self.assertEqual([s[0] for s in self.started], ['devbox1', 'notify'])
        self.assertIn('port --commit ' + self.nightly, self.started[0][1])
        self.assertIn('port running on devbox1', self.started[1][1])
        # The next hourly run stops before it touches the checkout or runs a check.
        with patch.object(customize, 'prepare', side_effect=AssertionError('applied the patches again')):
            with self.assertRaises(customize.PortHandedOff) as again:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertIn('was handed to devbox1 at', str(again.exception))
        self.assertEqual(len(self.started), 2)

    def test_changed_patches_after_a_hand_off_are_applied_again(self):
        customize.save(customize.HANDOFFS, {self.nightly: {'porter': 'devbox1', 'at': 1e12, 'recipes': ['old']}})
        with patch.object(customize.time, 'time', lambda: 1e12 + 60):
            customize.handed_off_already(self.nightly, 'n2', clock=lambda: 1e12 + 60)  # no raise
            customize.save(customize.HANDOFFS, {self.nightly: {'porter': 'devbox1', 'at': 1e12,
                                                               'recipes': [customize.recipe_hash(full=True)]}})
            with self.assertRaises(customize.PortHandedOff):
                customize.handed_off_already(self.nightly, 'n2', clock=lambda: 1e12 + 60)
        # After the quiet window it tries again.
        customize.handed_off_already(self.nightly, 'n2', clock=lambda: 1e12 + customize.HANDOFF_QUIET + 1)

    def test_the_porter_itself_hands_its_server_run_to_port(self):
        spawned = []
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'this_machine', lambda machines: machines[1]), \
                patch.object(customize, 'spawn_detached', lambda argv, name: spawned.append(argv)), \
                patch.object(customize, 'agent_fix', side_effect=AssertionError('ported inline')):
            with self.assertRaises(customize.PortHandedOff):
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertEqual(spawned[0][2:], customize.port_command(customize.porter_machine(), self.nightly, 'n2'))
        self.assertTrue(self.clean())
        self.assertEqual([s[0] for s in self.started], ['notify'])

    def test_an_unreachable_porter_is_reported_once_per_window(self):
        args = argparse.Namespace(resume=False, skip_checks=True, fix=None, background=True)
        with patch.object(customize, 'ssh_target', lambda machine: None):
            for _ in range(2):
                with self.assertRaises(customize.NeedsFix) as stop:
                    self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
                self.assertNotIsInstance(stop.exception, customize.PortHandedOff)
                self.assertIn('unreachable', str(stop.exception))
                self.assertTrue(self.clean())
        notes = [s for s in self.started if s[0] == 'notify']
        self.assertEqual(len(notes), 1)
        self.assertIn('unreachable', notes[0][1])
        self.assertTrue(customize.load(customize.HANDOFFS)[self.nightly]['unreachable'])

    def test_a_repo_outside_home_is_passed_as_an_absolute_path(self):
        with patch.object(customize, 'REPO', Path('/srv/t3code-customize-tt')):
            self.assertEqual(customize.repo_path(), '/srv/t3code-customize-tt')
            line = customize.remote_port_line(customize.porter_machine(), 'f' * 40, 'n2', customize.repo_path())
        self.assertIn('python3 /srv/t3code-customize-tt/t3code-customize port', line)
        self.assertNotIn('$HOME"//srv', line)

    def test_a_run_someone_watches_does_not_hand_over(self):
        args = argparse.Namespace(resume=False, skip_checks=True, fix=None, background=False)
        with patch.object(customize, 'interactive', lambda: False):
            with self.assertRaises(customize.NeedsFix) as stop:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertNotIsInstance(stop.exception, customize.PortHandedOff)
        self.assertEqual(self.started, [])


class FindAgentTest(unittest.TestCase):
    def test_an_agent_in_local_bin_is_found_without_it_on_path(self):
        # zsh -lc over SSH reads no .zshrc, so units written from it lack ~/.local/bin.
        with tempfile.TemporaryDirectory() as home:
            folder = Path(home) / '.local/bin'
            folder.mkdir(parents=True)
            agent = folder / 'claude'
            agent.write_text('#!/bin/sh\n')
            agent.chmod(0o755)
            with patch.object(customize, 'HOME', Path(home)), patch.dict(os.environ, {'PATH': '/usr/bin:/bin'}):
                self.assertEqual(customize.choose_agent('claude'), 'claude')
                self.assertEqual(os.environ['PATH'].split(os.pathsep)[0], str(folder))

    def test_a_missing_agent_still_stops(self):
        with tempfile.TemporaryDirectory() as home, patch.object(customize, 'HOME', Path(home)), \
                patch.dict(os.environ, {'PATH': '/usr/bin:/bin'}):
            with self.assertRaises(customize.Stop):
                customize.choose_agent('claude')


class OneAgentSessionTest(Sandbox):
    def test_one_session_resolves_every_stage_and_the_run_does_not_start_another(self):
        sessions = []

        def agent(name, problem, target, version, log):
            sessions.append(problem)
            self.resolve('a.txt', '2\n')
            with self.assertRaises(customize.NeedsFix):
                self.cont()
            self.resolve('b.txt', '2\n')
            self.cont()
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'agent_fix', agent), patch.object(customize, 'choose_agent', lambda r: r), \
                patch.object(customize, 'install_dependencies', lambda env, log: None):
            ported, _ = self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log, handoff=False)
        self.assertTrue(ported)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(git(self.source, 'rev-list', '--count', self.nightly + '..HEAD'), '3')

    def test_an_unfinished_session_is_not_followed_by_a_second(self):
        sessions = []
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=False)
        with patch.object(customize, 'agent_fix', lambda *a: sessions.append(a)), \
                patch.object(customize, 'choose_agent', lambda r: r):
            with self.assertRaises(customize.NeedsFix):
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertEqual(len(sessions), 1)
        # Someone watches this run: the stop stays for them.
        self.assertTrue(customize.rebase_in_progress())

    def test_an_unattended_session_that_gives_up_leaves_the_checkout_clean_and_says_so(self):
        def agent(name, problem, target, version, log):
            # Mid-fix: resolved the rebase, then left a half edit and no rebase behind.
            self.resolve('a.txt', '2\n')
            with self.assertRaises(customize.NeedsFix):
                self.cont()
            self.resolve('b.txt', '2\n')
            self.cont()
            (self.source / 'a.txt').write_text('half done\n')
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'agent_fix', agent), patch.object(customize, 'choose_agent', lambda r: r):
            with self.assertRaises(customize.NeedsFix):
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log, handoff=False)
        self.assertTrue(self.clean())
        self.assertEqual(customize.run_marker(), {})
        self.assertIn('failed', customize.load(customize.PORTS)['n2'])
        self.assertIn('The port to n2 failed', self.notes[0])
        # The next unattended run starts over instead of stopping at the guard.
        with self.assertRaises(customize.NeedsFix) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertIn('The shared patches conflict', str(stop.exception))

    def test_a_port_waiting_for_review_is_not_ported_again(self):
        customize.save(customize.PORTS, {'n2': {'url': 'https://example.test/pr/9', 'layers': ['shared', 'patches-tt', 'patches-ios']}})
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'agent_fix', side_effect=AssertionError('ported again')), \
                patch.object(customize, 'choose_agent', lambda r: r):
            with self.assertRaises(customize.PortHandedOff) as stop:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertIn('waits for review: https://example.test/pr/9', str(stop.exception))
        self.assertTrue(self.clean())

    def test_the_prompt_points_at_the_porting_docs_and_the_loop(self):
        prompt = customize.agent_prompt('conflict', self.nightly, 'n2')
        self.assertIn('docs/porting.md', prompt)
        self.assertIn('docs/fork-changes.md', prompt)
        self.assertIn('t3code-customize continue --source', prompt)
        self.assertIn('t3code-customize checks --source', prompt)
        self.assertNotIn('AGENTS.md', prompt)


class PortPendingTest(Sandbox):
    def test_a_published_port_counts_only_with_the_ios_layer(self):
        customize.save(customize.PORTS, {'n2': {'url': 'u', 'layers': ['shared', 'patches-tt']}})
        self.assertIsNone(customize.port_pending('n2'))
        customize.save(customize.PORTS, {'n2': {'url': 'u', 'layers': ['shared', 'patches-tt', 'patches-ios']}})
        self.assertEqual(customize.port_pending('n2'), 'u')

    def test_an_open_port_branch_pr_counts(self):
        prs = [{'url': 'https://x/pull/3', 'headRefName': 'port/nightly-n2-2'},
               {'url': 'https://x/pull/4', 'headRefName': 'port/nightly-n3'}]
        with patch.object(customize, 'fork_repo', lambda: 'o/r'), \
                patch.object(customize.shutil, 'which', lambda n: n), \
                patch.object(customize.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 0, json.dumps(prs), '')):
            self.assertEqual(customize.port_pending('n2'), 'https://x/pull/3')
            self.assertIsNone(customize.port_pending('n1'))


class HistoryRecipeTest(Sandbox):
    def test_a_failing_patch_set_from_history_leaves_no_stop_behind(self):
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'older_than_patches', lambda target: True), \
                patch.object(customize, 'use_older_recipe', lambda target, log: None):
            with self.assertRaises(customize.NeedsFix) as stop:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertIn('made for this nightly fails here', str(stop.exception))
        self.assertTrue(self.clean())
        self.assertEqual(customize.run_marker(), {})


def dead_pid():
    child = subprocess.Popen([sys.executable, '-c', 'pass'])
    child.wait()
    return child.pid


class KilledSessionTest(Sandbox):
    """A run killed during its agent session (reboot, OOM, unit stopped) never records its fingerprint."""

    def killed(self, pid):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        customize.update_run_marker(stopped=None, agent={'pid': pid, 'ticks': customize.process_ticks(pid)})

    def test_a_dead_session_nobody_claimed_is_aborted(self):
        self.killed(dead_pid())
        self.resolve('a.txt', 'half done\n')  # what the agent got to before the kill
        with self.assertRaises(customize.NeedsFix) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertIn('The shared patches conflict', str(stop.exception))

    def test_a_live_session_stays_protected(self):
        self.killed(os.getpid())
        with self.assertRaises(customize.Stop) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertIn('stopped rebase or git am', str(stop.exception))

    def test_a_claimed_checkout_stays_protected_after_a_kill(self):
        self.killed(dead_pid())
        with self.assertRaises(customize.NeedsFix):
            self.cont()
        with self.assertRaises(customize.Stop) as stop:
            self.quiet(self.prepare, unattended=True)
        self.assertNotIsInstance(stop.exception, customize.NeedsFix)

    def test_the_session_is_in_the_marker_while_it_runs_and_the_fingerprint_after(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        seen = []
        real = customize.subprocess.run

        def run(args, *rest, **kwargs):
            if kwargs.get('input') is not None:
                seen.append(customize.run_marker())
                return subprocess.CompletedProcess(args, 0)
            return real(args, *rest, **kwargs)
        with patch.object(customize.subprocess, 'run', run), patch.object(customize, 'command_args', lambda a, env=None: a):
            self.quiet(customize.agent_fix, 'claude', 'conflict', self.nightly, 'n2', self.log)
        self.assertEqual(seen[0]['agent']['pid'], os.getpid())
        self.assertFalse(seen[0]['stopped'])
        after = customize.run_marker()
        self.assertIsNone(after['agent'])
        self.assertEqual(after['stopped'], customize.checkout_fingerprint())


class FailedPortTest(Sandbox):
    def args(self, force=False):
        return argparse.Namespace(no_pull=True, resume=False, version='n2', commit=None, force=force, dry_run=False)

    def test_a_recent_failure_stops_the_next_port_and_is_reported_once(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        self.quiet(customize.port_failed, 'n2', 'conflict', self.log)
        self.notes.clear()
        with patch.object(customize, 'port_pending', lambda v: None), \
                patch.object(customize, 'tool_log', side_effect=AssertionError('ported again')):
            for _ in range(2):
                ported, out = self.quiet(customize.cmd_port, self.args())
                self.assertFalse(ported)
                self.assertIn('failed at', out)
        self.assertEqual(len(self.notes), 1)
        self.assertIn('port --force', self.notes[0])

    def test_force_changed_patches_or_time_try_again(self):
        customize.save(customize.PORTS, {'n2': {'failed': 'log', 'failedEpoch': 1e12, 'failedRecipe': customize.recipe_hash(full=True)}})
        self.assertIsNotNone(customize.recent_failure('n2', clock=lambda: 1e12 + 60))
        self.assertIsNone(customize.recent_failure('n2', clock=lambda: 1e12 + customize.HANDOFF_QUIET + 1))
        with patch.object(customize, 'recipe_hash', return_value='other'):
            self.assertIsNone(customize.recent_failure('n2', clock=lambda: 1e12 + 60))
        with patch.object(customize, 'recent_failure', side_effect=AssertionError('checked with --force')), \
                patch.object(customize, 'port_pending', lambda v: None), \
                patch.object(customize, 'tool_log', side_effect=RuntimeError('ported')):
            with self.assertRaises(RuntimeError):
                self.quiet(customize.cmd_port, self.args(force=True))


class SpawnDetachedTest(Sandbox):
    def test_a_failed_systemd_run_falls_back_to_a_new_session(self):
        started = []
        with patch.dict(os.environ, INVOCATION_ID='x'), patch.object(customize.shutil, 'which', lambda n: n), \
                patch.object(customize.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, '', 'Failed to connect to bus')), \
                patch.object(customize.subprocess, 'Popen', lambda argv, **k: started.append((argv, k))):
            self.assertEqual(customize.spawn_detached(['true'], 'port'), 'setsid')
        self.assertTrue(started[0][1]['start_new_session'])
        self.assertIn('systemd-run failed', (self.cache / 'logs/port.log').read_text())

    def test_a_start_that_fails_is_a_recorded_hand_off_without_a_traceback(self):
        machines = {'machines': [{'name': 'devbox1', 'hostname': 'devbox1', 'kind': 'server', 'fix': 'claude'}]}
        customize.MACHINES.write_text(json.dumps(machines))

        real = subprocess.Popen

        def fail(argv, *rest, **kwargs):
            if argv[0] == sys.executable:
                raise OSError('no such file')
            return real(argv, *rest, **kwargs)
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'this_machine', lambda m: m[0]), patch.dict(os.environ, {'INVOCATION_ID': ''}), \
                patch.object(customize.subprocess, 'Popen', fail):
            for _ in range(2):
                with self.assertRaises(customize.NeedsFix) as stop:
                    self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
                self.assertNotIsInstance(stop.exception, customize.PortHandedOff)
                self.assertIn('Could not start port', str(stop.exception))
                self.assertTrue(self.clean())
        self.assertEqual(len(self.notes), 1)
        self.assertIn('no such file', customize.load(customize.HANDOFFS)[self.nightly]['error'])


class StuckMessageTest(Sandbox):
    def test_a_stopped_port_names_port_continue_and_checks(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare()
        with patch.object(customize, 'COMMAND', 'port'):
            message = customize.stuck_message('conflict', self.nightly)
        self.assertIn('t3code-customize continue --source', message)
        self.assertIn('t3code-customize checks --source', message)
        self.assertIn('port --source', message)
        self.assertIn('--resume --version n2', message)
        self.assertIn('--version n2 --fix claude', message)
        self.assertNotIn(' ios', message)


class OpenPrsTest(unittest.TestCase):
    def report(self, result):
        with patch.object(customize, 'fork_repo', lambda: 'o/r'), patch.object(customize.shutil, 'which', lambda n: n):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                customize.report_open_prs(run=lambda *a, **k: result)
        return out.getvalue()

    def test_one_line_per_open_pr(self):
        prs = [{'number': 20, 'title': 'feat: x', 'headRefName': 'feat/x', 'isDraft': False},
               {'number': 21, 'title': 'chore: port', 'headRefName': 'port/nightly-n2', 'isDraft': True}]
        out = self.report(subprocess.CompletedProcess([], 0, json.dumps(prs), ''))
        self.assertIn('Open PRs (o/r): 2', out)
        self.assertIn('#20 feat: x (feat/x)', out)
        self.assertIn('#21 chore: port (port/nightly-n2, draft)', out)

    def test_offline_prints_one_skip_line(self):
        out = self.report(subprocess.CompletedProcess([], 1, '', 'error connecting'))
        self.assertEqual(out.strip(), 'Open PRs: skipped, gh could not reach GitHub (offline or not signed in).')


if __name__ == '__main__':
    unittest.main()
