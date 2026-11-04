"""fleet keeps every machine's checkout on git (sync_repo), runs a Mac's update through its LaunchAgent
(agent_run_snippet) and `ios` stops early without the keychain (keychain_reachable)."""
import argparse
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_fleet_sync', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

ENV = dict(GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t',
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')


def facts(**values):
    base = {'repo': True, 'branch': 'main', 'head': 'a' * 40, 'target': 'b' * 40, 'ancestor': True,
            'dirty': [], 'differing': []}
    return dict(base, **values)


class SyncDecisionTest(unittest.TestCase):
    def test_a_clean_checkout_behind_fast_forwards(self):
        self.assertEqual(customize.sync_decision(facts())[0], 'ff')

    def test_a_clean_checkout_at_the_target_is_current(self):
        self.assertEqual(customize.sync_decision(facts(head='b' * 40))[0], 'current')

    def test_dirt_identical_to_the_target_is_reset(self):
        # What an older fleet's file copy left: modified and untracked files that equal origin/main,
        # next to files that only changed upstream.
        action, detail = customize.sync_decision(facts(dirty=['patches-tt/0001.patch', 'new.json'],
                                                       differing=['docs/other.md']))
        self.assertEqual(action, 'reset')
        self.assertIn('2 changed', detail)

    def test_a_real_local_change_is_refused_and_named(self):
        action, detail = customize.sync_decision(facts(dirty=['a.py', 'b.py'], differing=['b.py']))
        self.assertEqual(action, 'refuse')
        self.assertIn('b.py', detail)
        self.assertNotIn('a.py', detail)

    def test_local_commits_another_branch_or_no_target_are_refused(self):
        self.assertEqual(customize.sync_decision(facts(ancestor=False))[0], 'refuse')
        self.assertEqual(customize.sync_decision(facts(branch='work'))[0], 'refuse')
        self.assertEqual(customize.sync_decision(facts(branch=''))[0], 'refuse')
        self.assertEqual(customize.sync_decision(facts(target=''))[0], 'refuse')
        self.assertEqual(customize.sync_decision(facts(error='moved'))[0], 'refuse')

    def test_untracked_extras_count_for_nothing(self):
        self.assertEqual(customize.sync_decision(facts(dirty=['skills-lock.json'], differing=['skills-lock.json'],
                                                       extra=['skills-lock.json']))[0], 'ff')

    def test_no_git_checkout_falls_back_to_the_copy(self):
        self.assertEqual(customize.sync_decision({'exists': True, 'repo': False})[0], 'copy')

    def test_a_missing_checkout_is_never_created(self):
        self.assertEqual(customize.sync_decision({'exists': False, 'repo': False})[0], 'refuse')


class CheckoutRootTest(unittest.TestCase):
    def test_a_worktree_syncs_the_main_checkouts_path(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            main, tree = home / 'Devops/repo', home / '.t3/worktrees/repo/t3-1'
            main.mkdir(parents=True)

            def git(*args):
                subprocess.run(['git', *args], cwd=main, check=True, capture_output=True, env=dict(os.environ, **ENV))
            git('init', '-q', '-b', 'main')
            git('commit', '-q', '--allow-empty', '-m', 'one')
            git('worktree', 'add', '-q', '-b', 'work', str(tree))
            with patch.object(customize, 'REPO', tree), patch.object(customize, 'HOME', home):
                self.assertEqual(customize.repo_path(), 'Devops/repo')
            with patch.object(customize, 'REPO', main), patch.object(customize, 'HOME', home):
                self.assertEqual(customize.repo_path(), 'Devops/repo')


class SyncRepoTest(unittest.TestCase):
    """sync_repo against real git: a bare origin, our checkout and the machine's checkout under a
    fake $HOME; `remote` runs the command here with that $HOME."""

    def git(self, cwd, *args):
        return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True,
                              env=dict(os.environ, **ENV)).stdout.strip()

    def commit(self, cwd, name, text):
        (Path(cwd) / name).parent.mkdir(parents=True, exist_ok=True)
        (Path(cwd) / name).write_text(text)
        self.git(cwd, 'add', '-A')
        self.git(cwd, 'commit', '-qm', name)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.origin, self.ours, self.home = base / 'origin.git', base / 'ours', base / 'home'
        self.git(base, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.git(base, 'clone', '-q', str(self.origin), str(self.ours))
        self.git(self.ours, 'checkout', '-q', '-b', 'main')
        self.commit(self.ours, 'patches-tt/0001.patch', 'one\n')
        self.git(self.ours, 'push', '-q', '-u', 'origin', 'main')
        self.mac = self.home / 'repo'
        self.git(base, 'clone', '-q', str(self.origin), str(self.mac))
        # Upstream moves on after the Mac cloned.
        self.commit(self.ours, 'patches-tt/0001.patch', 'one, ported\n')
        self.commit(self.ours, 'patches-tt/0002.patch', 'two\n')
        self.git(self.ours, 'push', '-q', 'origin', 'main')
        self.lines = []

    def remote(self, alias, command, **kwargs):
        env = dict(os.environ, HOME=str(self.home), **ENV)
        return subprocess.run(['sh', '-c', command], env=env, cwd=str(self.home), **kwargs)

    def sync(self, origin_reachable=True):
        if not origin_reachable:
            self.git(self.mac, 'remote', 'set-url', 'origin', str(self.home / 'gone.git'))
        with patch.object(customize, 'remote', self.remote), patch.object(customize, 'REPO', self.ours), \
                patch.object(customize, 'HOME', self.home), \
                patch.object(customize, 'remote_identity', return_value={'same': True}):
            customize.sync_repo('mac', 'repo', {'same': True}, self.lines.append)

    def mac_state(self):
        return (self.git(self.mac, 'rev-parse', 'HEAD'), self.git(self.mac, 'status', '--porcelain'))

    def ours_head(self):
        return self.git(self.ours, 'rev-parse', 'HEAD')

    def test_a_clean_checkout_fast_forwards(self):
        self.sync()
        self.assertEqual(self.mac_state(), (self.ours_head(), ''))

    def test_files_an_old_fleet_copied_are_reset_to_the_same_commit(self):
        # The file copy wrote origin/main's files into the Mac's tree without moving git.
        for name in ('patches-tt/0001.patch', 'patches-tt/0002.patch'):
            (self.mac / name).write_text((self.ours / name).read_text())
        self.sync()
        self.assertEqual(self.mac_state(), (self.ours_head(), ''))
        self.assertTrue(any('already match' in line for line in self.lines))

    def test_a_real_local_change_stops_and_is_kept(self):
        (self.mac / 'patches-tt/0001.patch').write_text('my own edit\n')
        before = self.git(self.mac, 'rev-parse', 'HEAD')
        with self.assertRaises(customize.Stop) as stopped:
            self.sync()
        self.assertIn('patches-tt/0001.patch', str(stopped.exception))
        self.assertEqual(self.git(self.mac, 'rev-parse', 'HEAD'), before)
        self.assertEqual((self.mac / 'patches-tt/0001.patch').read_text(), 'my own edit\n')

    def test_untracked_files_origin_lacks_are_kept_and_do_not_block(self):
        # A checkout's own installed skills, next to files an old fleet copied in.
        (self.mac / '.agents/skills/x').mkdir(parents=True)
        (self.mac / '.agents/skills/x/SKILL.md').write_text('mine\n')
        (self.mac / 'patches-tt/0002.patch').write_text('two\n')
        self.sync()
        head, status = self.mac_state()
        self.assertEqual(head, self.ours_head())
        self.assertEqual(status, '?? .agents/')
        self.assertEqual((self.mac / '.agents/skills/x/SKILL.md').read_text(), 'mine\n')

    def test_an_untracked_file_that_differs_from_origin_stops(self):
        (self.mac / 'patches-tt/0002.patch').write_text('my own two\n')
        with self.assertRaises(customize.Stop) as stopped:
            self.sync()
        self.assertIn('patches-tt/0002.patch', str(stopped.exception))
        self.assertEqual((self.mac / 'patches-tt/0002.patch').read_text(), 'my own two\n')

    def test_a_machine_without_the_checkout_is_left_alone(self):
        subprocess.run(['rm', '-r', str(self.mac)], check=True)
        with self.assertRaises(customize.Stop) as stopped:
            self.sync()
        self.assertIn('no checkout', str(stopped.exception))
        self.assertFalse(self.mac.exists())

    def test_without_github_the_commits_come_as_a_bundle(self):
        self.sync(origin_reachable=False)
        self.assertEqual(self.mac_state(), (self.ours_head(), ''))
        self.assertTrue(any('bundle' in line for line in self.lines))
        self.assertEqual(list(self.home.glob('.t3code-customize-sync-*')), [])


FAKE_LAUNCHCTL = '''#!/bin/sh
# print: "running" for the first RUNS prints after a kickstart, then the exit code in EXIT.
state="$FAKE_DIR/state"
case "$1" in
  kickstart) echo kickstart >> "$FAKE_DIR/calls"; echo 0 > "$state"; echo "==> Rebuilt" >> "$FAKE_LOG" ;;
  print)
    if [ -f "$state" ]; then
      n=$(cat "$state"); echo $((n + 1)) > "$state"
      if [ "$n" -lt "$RUNS" ]; then printf '\\tstate = running\\n'; exit 0; fi
      [ "$n" -eq "$RUNS" ] && echo "iOS app uploaded" >> "$FAKE_LOG"
    fi
    printf '\\tstate = not running\\n\\t\\tstate = active\\n\\tlast exit code = %s\\n' "$EXIT" ;;
esac
'''


class AgentRunTest(unittest.TestCase):
    def run_agent(self, exit_code=0, runs=2):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'bin').mkdir()
            (home / 'bin/launchctl').write_text(FAKE_LAUNCHCTL)
            (home / 'bin/launchctl').chmod(0o755)
            log = home / '.cache/t3code-customize/logs/autoupdate.log'
            log.parent.mkdir(parents=True)
            log.write_text('an older run\n')
            argv = customize.agent_run_command(1)
            snippet = customize.agent_run_snippet().replace('time.sleep(5)', 'time.sleep(0.01)')
            env = dict(os.environ, HOME=str(home), PATH=f"{home / 'bin'}{os.pathsep}{os.environ['PATH']}",
                       FAKE_DIR=str(home), FAKE_LOG=str(log), RUNS=str(runs), EXIT=str(exit_code))
            done = subprocess.run([sys.executable, *argv[1:]], input=snippet, capture_output=True, text=True,
                                  env=env, timeout=60)
            calls = (home / 'calls').read_text() if (home / 'calls').exists() else ''
            return done, calls

    def test_it_kickstarts_once_streams_the_new_log_and_returns_the_runs_code(self):
        done, calls = self.run_agent(exit_code=3)
        self.assertEqual(calls, 'kickstart\n')
        self.assertEqual(done.returncode, 3)
        self.assertIn('Rebuilt', done.stdout)
        self.assertIn('iOS app uploaded', done.stdout)
        self.assertNotIn('an older run', done.stdout)

    def test_a_clean_run_is_ok(self):
        self.assertEqual(self.run_agent()[0].returncode, 0)

    def test_the_command_names_the_launchagent_and_its_log(self):
        argv = customize.agent_run_command(30)
        self.assertEqual(argv[:3], ['python3', '-', customize.AUTOUPDATE_LABEL])
        self.assertTrue(argv[3].endswith('logs/autoupdate.log'))
        self.assertEqual(argv[-1], '30')


class FleetMacRouteTest(unittest.TestCase):
    """A Mac's update in fleet goes through the LaunchAgent; only --force/--fix rebuild directly."""

    def fleet(self, **values):
        args = argparse.Namespace(**dict({'foreground': True, 'no_pull': True, 'only': ['mbp'], 'fix': None,
                                          'force': False, 'wait_lock': 30}, **values))
        started = []

        class Done:
            def __init__(self, argv):
                self.stdout = iter(['line from ' + ' '.join(argv) + '\n'])

            def wait(self):
                return 0

        def popen(argv, **kwargs):
            started.append(argv[-1])

            class Pipe:
                def write(self, text):
                    pass

                def close(self):
                    pass
            done = Done(argv)
            done.stdin = Pipe()
            return done

        machines = {'machines': [{'name': 'mbp', 'kind': 'mac', 'ssh': ['mac'], 'ios': True}]}
        with patch.object(customize, 'load', return_value=machines), \
                patch.object(customize, 'ssh_target', return_value='mac'), \
                patch.object(customize, 'sync_repo'), patch.object(customize, 'this_machine', return_value=None), \
                patch.object(customize, 'repo_path', return_value='Devops/Personal/t3code-customize-tt'), \
                patch.object(customize, 'identity', return_value={}), patch.object(customize, 'say'), \
                patch.object(customize.subprocess, 'Popen', popen):
            customize.cmd_fleet(args)
        return started

    def test_a_mac_turns_autoupdate_on_then_runs_the_launchagent(self):
        started = self.fleet()
        self.assertEqual(len(started), 2)
        self.assertIn('autoupdate on --ios', started[0])
        self.assertIn(customize.AUTOUPDATE_LABEL, started[1])
        self.assertFalse(any(' update ' in line for line in started))

    def test_force_rebuilds_directly_first(self):
        started = self.fleet(force=True)
        self.assertIn('update --no-pull', started[0])
        self.assertIn('--force', started[0])
        self.assertIn(customize.AUTOUPDATE_LABEL, started[-1])


class KeychainTest(unittest.TestCase):
    def test_security_answering_36_means_no_keychain(self):
        self.assertFalse(customize.keychain_reachable(lambda *a, **k: argparse.Namespace(returncode=36)))
        self.assertTrue(customize.keychain_reachable(lambda *a, **k: argparse.Namespace(returncode=0)))

    def test_ios_stops_before_any_work_without_the_keychain(self):
        args = argparse.Namespace(app=None, no_pull=False, resume=False, force=False)
        with patch.object(customize, 'MAC', True), patch.object(customize.shutil, 'which', return_value='/bin/x'), \
                patch.object(customize, 'keychain_reachable', return_value=False), \
                patch.object(customize, 'ios_config') as config, patch.object(customize, 'pull_latest') as pull:
            with self.assertRaises(customize.Stop) as stopped:
                customize.cmd_ios(args)
        self.assertIn('keychain', str(stopped.exception))
        self.assertIn('launchctl kickstart', str(stopped.exception))
        config.assert_not_called()
        pull.assert_not_called()


if __name__ == '__main__':
    unittest.main()
