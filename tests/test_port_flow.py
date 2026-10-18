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
        for name, value in (('SOURCE', self.source), ('CACHE', self.cache), ('WITH_IOS', True),
                            ('DATA', root / 'data')):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(customize.use_recipe, customize.REPO)
        customize.use_recipe(self.recipe)
        self.log = (root / 'log').open('w+')
        self.addCleanup(self.log.close)

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
    def test_an_unattended_run_aborts_the_stop_an_unattended_run_left(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        self.assertTrue(customize.rebase_in_progress())
        with self.assertRaises(customize.NeedsFix) as stop:
            self.quiet(self.prepare, unattended=True)
        # It started over: the stop it reports is a fresh one, not the guard.
        self.assertIn('The shared patches conflict', str(stop.exception))

    def test_a_stop_a_person_or_agent_started_stays_protected(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=False)
        with self.assertRaises(customize.Stop) as stop:
            self.prepare(unattended=True)
        self.assertNotIsInstance(stop.exception, customize.NeedsFix)
        self.assertIn('stopped rebase or git am', str(stop.exception))
        self.assertTrue(customize.rebase_in_progress())

    def test_a_stop_without_a_marker_stays_protected(self):
        with self.assertRaises(customize.NeedsFix):
            self.prepare(unattended=True)
        (customize.git_dir() / customize.RUN_MARK).unlink()
        with self.assertRaises(customize.Stop) as stop:
            self.prepare(unattended=True)
        self.assertIn('stopped rebase or git am', str(stop.exception))


class ChecksStampTest(Sandbox):
    def setUp(self):
        super().setUp()
        git(self.source, 'checkout', '-q', '--detach', self.base)

    def test_checks_that_passed_on_this_commit_are_skipped(self):
        customize.save(customize.git_dir() / customize.CHECKS_STAMP,
                       {'head': git(self.source, 'rev-parse', 'HEAD'), 'lists': customize.check_lists_hash()})
        with patch.object(customize, 'run_bounded', side_effect=AssertionError('ran a check')):
            _, out = self.quiet(customize.checks, {}, self.log, self.base)
        self.assertIn('already passed on this commit', out)

    def test_a_new_commit_or_changed_check_list_runs_them_again(self):
        stamp = customize.git_dir() / customize.CHECKS_STAMP
        customize.save(stamp, {'head': self.base, 'lists': customize.check_lists_hash()})
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": ["x"]}\n')
        self.assertFalse(customize.checks_stamped())
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": []}\n')
        self.assertTrue(customize.checks_stamped())
        customize.save(stamp, {'head': self.nightly, 'lists': customize.check_lists_hash()})
        self.assertFalse(customize.checks_stamped())

    def test_passing_checks_write_the_stamp_and_force_ignores_it(self):
        calls = []

        def fake(args, env, log, timeout, cwd=None, merge=False):
            calls.append(args)
            return 0, ''
        (self.recipe / 'checks.json').write_text('{"tests": [], "typecheck": ["packages/x"]}\n')
        with patch.object(customize, 'run_bounded', fake):
            self.quiet(customize.checks, {}, self.log, self.base)
            self.assertTrue(customize.checks_stamped())
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
        for name, value in (('REPO', self.repo), ('CACHE', self.cache)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_newest_patch_set_made_for_that_nightly_is_used(self):
        self.assertEqual(customize.recipe_for('b' * 40), self.feature)
        self.assertEqual(customize.recipe_for('a' * 40), self.first)
        folder = customize.extract_recipe(self.feature)
        self.assertEqual((folder / 'patches-tt/0001-x.patch').read_text(), 'v3\n')
        self.assertEqual((folder / 'patches-port/base.txt').read_text().strip(), 'b' * 40)

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
        # The next hourly run hands nothing over again, and stays clean too.
        with patch.object(customize, 'interactive', lambda: False):
            with self.assertRaises(customize.PortHandedOff) as again:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertIn('handed to devbox1 already', str(again.exception))
        self.assertEqual(len(self.started), 2)
        self.assertFalse(customize.rebase_in_progress())

    def test_a_run_someone_watches_does_not_hand_over(self):
        args = argparse.Namespace(resume=False, skip_checks=True, fix=None, background=False)
        with patch.object(customize, 'interactive', lambda: False):
            with self.assertRaises(customize.NeedsFix) as stop:
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertNotIsInstance(stop.exception, customize.PortHandedOff)
        self.assertEqual(self.started, [])


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
            ported, _ = self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertTrue(ported)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(git(self.source, 'rev-list', '--count', self.nightly + '..HEAD'), '3')

    def test_an_unfinished_session_is_not_followed_by_a_second(self):
        sessions = []
        args = argparse.Namespace(resume=False, skip_checks=True, fix='claude', background=True)
        with patch.object(customize, 'agent_fix', lambda *a: sessions.append(a)), \
                patch.object(customize, 'choose_agent', lambda r: r):
            with self.assertRaises(customize.NeedsFix):
                self.quiet(customize.apply_patches, args, self.nightly, 'n2', {}, self.log)
        self.assertEqual(len(sessions), 1)

    def test_the_prompt_points_at_the_porting_docs_and_the_loop(self):
        prompt = customize.agent_prompt('conflict', self.nightly, 'n2')
        self.assertIn('docs/porting.md', prompt)
        self.assertIn('docs/fork-changes.md', prompt)
        self.assertIn('t3code-customize continue --source', prompt)
        self.assertIn('t3code-customize checks --source', prompt)
        self.assertNotIn('AGENTS.md', prompt)


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
