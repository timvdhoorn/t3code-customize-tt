import argparse
import contextlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_cover', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

OLD = '0.1.10-nightly.20261112.4564'
NEW = '0.1.10-nightly.20261112.4580'
NEWER = '0.1.10-nightly.20261113.4601'
FILE = customize.COVERED_NIGHTLY

# A gh that records its calls and plays the parts of a PR flow against a bare origin: "pr create"
# prints a URL, "pr merge" fast-forwards main to the PR's branch.
FAKE_GH = """#!/bin/sh
echo "$@" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "auth status") exit "${FAKE_GH_AUTH:-0}" ;;
  "pr view") exit 1 ;;
  "pr create") [ -n "$FAKE_GH_FAIL" ] && { echo "boom" >&2; exit 1; }; echo "https://github.com/o/r/pull/7" ;;
  "pr merge") git --git-dir="$FAKE_GH_ORIGIN" update-ref refs/heads/main "refs/heads/$3" ;;
esac
"""


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


class CoverAdvanceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.origin = self.root / 'origin.git'
        self.repo = self.root / 'repo'
        git(self.root, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        git(self.root, 'clone', '-q', str(self.origin), str(self.repo))
        (self.repo / FILE).write_text(OLD + '\n')
        (self.repo / 'patches-tt').mkdir()
        (self.repo / 'patches-tt/0001-a.patch').write_text('a\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'init')
        git(self.repo, 'push', '-q', 'origin', 'HEAD:main')
        git(self.repo, 'fetch', '-q', 'origin')
        git(self.repo, 'branch', '-q', '--set-upstream-to=origin/main')
        self.log = self.root / 'gh.log'
        self.log.write_text('')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        env = {'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}', 'FAKE_GH_LOG': str(self.log),
               'FAKE_GH_ORIGIN': str(self.origin)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.notes = []
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name, value in (('REPO', self.repo), ('RECIPE', self.repo), ('CACHE', self.root / 'cache'),
                            ('notify', lambda title, text: self.notes.append(text)), ('say', lambda *a: None)):
            stack.enter_context(patch.object(customize, name, value))
        (self.root / 'cache').mkdir()
        self.spawn = stack.enter_context(patch.object(customize, 'spawn_detached'))
        self.args = argparse.Namespace(skip_checks=False)

    def calls(self):
        return [line.split()[:2] for line in self.log.read_text().splitlines()]

    def origin_file(self):
        return git(self.root, '--git-dir', str(self.origin), 'show', f'main:{FILE}')

    def test_a_newer_nightly_is_merged_into_main_and_this_checkout_follows(self):
        customize.publish_cover(self.args, NEW)
        self.assertEqual(self.origin_file(), NEW)
        self.assertEqual((self.repo / FILE).read_text(), NEW + '\n')
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertIn(['pr', 'merge'], self.calls())
        self.assertEqual(self.notes, [])
        self.spawn.assert_not_called()  # nothing was rebuilt, so no fleet run
        # The PR holds covered-nightly.txt and nothing else.
        shown = git(self.repo, 'show', '--name-only', '--format=%s', 'HEAD').splitlines()
        self.assertEqual([line for line in shown if line], [f'chore: cover nightly {NEW}', FILE])

    def test_the_version_never_goes_down_and_an_equal_one_is_a_no_op(self):
        for version in (OLD, '0.1.9-nightly.20261201.1'):
            customize.publish_cover(self.args, version)
        customize.publish_cover(self.args, OLD)
        self.assertEqual(self.origin_file(), OLD)
        self.assertEqual([c for c in self.calls() if c[0] == 'pr'], [])
        customize.publish_cover(self.args, NEW)
        customize.publish_cover(self.args, NEW)
        customize.publish_cover(self.args, OLD)
        self.assertEqual(self.origin_file(), NEW)
        self.assertEqual(self.calls().count(['pr', 'merge']), 1)

    def test_a_file_missing_on_main_is_created(self):
        git(self.repo, 'rm', '-q', FILE)
        git(self.repo, 'commit', '-qm', 'drop')
        git(self.repo, 'push', '-q', 'origin', 'HEAD:main')
        customize.publish_cover(self.args, NEW)
        self.assertEqual(self.origin_file(), NEW)

    def test_nothing_happens_when_the_run_did_not_prove_the_patches(self):
        cases = (('checks skipped', argparse.Namespace(skip_checks=True), NEW, {}),
                 ('not a nightly', self.args, '40526f96f6ae', {}),
                 ('no version', self.args, None, {}),
                 ('an older patch set was applied', self.args, NEW, {'RECIPE': self.root / 'older'}))
        for name, args, version, overrides in cases:
            with contextlib.ExitStack() as stack:
                for key, value in overrides.items():
                    stack.enter_context(patch.object(customize, key, value))
                customize.publish_cover(args, version)
            self.assertEqual(self.calls(), [], name)
        self.assertEqual(self.origin_file(), OLD)

    def test_a_machine_that_cannot_publish_does_nothing(self):
        with patch.dict(os.environ, {'FAKE_GH_AUTH': '1'}):
            customize.publish_cover(self.args, NEW)
        self.assertEqual(self.calls(), [['auth', 'status']])
        with patch.object(customize.shutil, 'which', return_value=None):
            customize.publish_cover(self.args, NEW)
        no_git = self.root / 'no-git'
        no_git.mkdir()
        with patch.object(customize, 'REPO', no_git):
            customize.publish_cover(self.args, NEW)
        self.assertEqual(self.calls(), [['auth', 'status']])
        self.assertEqual(self.origin_file(), OLD)
        self.assertEqual(self.notes, [])

    def test_a_checkout_behind_main_opens_a_pr_that_waits_and_stays_clean(self):
        other = self.root / 'other'
        git(self.root, 'clone', '-q', str(self.origin), str(other))
        (other / 'README.md').write_text('x')
        git(other, 'add', '.')
        git(other, 'commit', '-qm', 'more')
        git(other, 'push', '-q', 'origin', 'HEAD:main')
        customize.publish_cover(self.args, NEW)
        self.assertNotIn(['pr', 'merge'], self.calls())
        self.assertEqual(self.origin_file(), OLD)
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertIn('waits for review', self.notes[0])

    def test_unpublished_patch_changes_here_block_the_cover(self):
        (self.repo / 'patches-tt/0001-a.patch').write_text('changed\n')
        customize.publish_cover(self.args, NEW)
        self.assertEqual([c for c in self.calls() if c[0] == 'pr'], [])
        self.assertEqual(self.origin_file(), OLD)
        self.assertEqual((self.repo / FILE).read_text(), OLD + '\n')
        self.assertEqual(git(self.repo, 'status', '--porcelain'), 'M patches-tt/0001-a.patch')

    def test_another_changed_file_keeps_the_pr_open(self):
        (self.repo / 'checks-tt.json').write_text('[]')
        git(self.repo, 'add', 'checks-tt.json')
        git(self.repo, 'commit', '-qm', 'checks')
        (self.repo / 'checks-tt.json').write_text('["x"]')
        customize.publish_cover(self.args, NEW)
        self.assertNotIn(['pr', 'merge'], self.calls())
        self.assertEqual(self.origin_file(), OLD)

    def test_a_failure_notifies_restores_the_file_and_does_not_raise(self):
        with patch.dict(os.environ, {'FAKE_GH_FAIL': '1'}):
            customize.publish_cover(self.args, NEW)
        self.assertEqual((self.repo / FILE).read_text(), OLD + '\n')
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertIn('failed', self.notes[0])
        self.assertEqual(self.origin_file(), OLD)

    def test_the_cover_branch_never_blocks_a_port_of_the_same_nightly(self):
        customize.publish_cover(self.args, NEW)
        self.assertEqual(self.calls().count(['pr', 'create']), 1)
        create = next(l for l in self.log.read_text().splitlines() if l.startswith('pr create'))
        self.assertIn(f'--head cover/nightly-{NEW}', create)
        self.assertNotIn('port/nightly', create)


class ServerAndPortHookTest(unittest.TestCase):
    def test_port_covers_a_clean_nightly_but_not_a_dry_run(self):
        for dry_run in (False, True):
            args = argparse.Namespace(no_pull=True, resume=False, version=NEW, commit=None, force=False,
                                      dry_run=dry_run, skip_checks=False)
            with patch.object(customize, 'port_pending', return_value=None), \
                    patch.object(customize, 'recent_failure', return_value=None), \
                    patch.object(customize, 'tool_log', contextlib.nullcontext), \
                    patch.object(customize, 'ensure_node'), patch.object(customize, 'build_env', return_value={}), \
                    patch.object(customize, 'ensure_commit', return_value='a' * 40), \
                    patch.object(customize, 'choose_shared'), patch.object(customize, 'say'), \
                    patch.object(customize, 'older_than_patches', return_value=False), \
                    patch.object(customize, 'apply_patches', return_value=False), \
                    patch.object(customize, 'publish_cover') as cover:
                self.assertFalse(customize.cmd_port(args))
            self.assertEqual(cover.called, not dry_run)
            if not dry_run:
                cover.assert_called_once_with(args, NEW)


if __name__ == '__main__':
    unittest.main()
