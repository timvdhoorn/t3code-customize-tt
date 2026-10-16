import argparse
import importlib.machinery
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_unattended', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


def state_db(path, runs):
    """A statev2.sqlite with the two projection tables the idle check reads."""
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE orchestration_v2_projection_threads (thread_id TEXT PRIMARY KEY, title TEXT,'
               ' deleted_at TEXT)')
    db.execute('CREATE TABLE orchestration_v2_projection_runs (run_id TEXT PRIMARY KEY, thread_id TEXT, status TEXT)')
    for index, (title, status, deleted) in enumerate(runs):
        db.execute('INSERT INTO orchestration_v2_projection_threads VALUES (?, ?, ?)',
                   (f't{index}', title, '2026-10-16' if deleted else None))
        db.execute('INSERT INTO orchestration_v2_projection_runs VALUES (?, ?, ?)', (f'r{index}', f't{index}', status))
    db.commit()
    db.close()


class BusyThreadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'statev2.sqlite'

    def test_every_live_run_status_counts_as_busy(self):
        state_db(self.db, [(status, status, False) for status in customize.ACTIVE_RUN_STATUSES])
        self.assertEqual(customize.busy_threads(self.db), sorted(customize.ACTIVE_RUN_STATUSES))

    def test_finished_runs_and_deleted_threads_are_idle(self):
        state_db(self.db, [('done', 'completed', False), ('stopped', 'interrupted', False),
                           ('failed', 'failed', False), ('gone', 'running', True)])
        self.assertEqual(customize.busy_threads(self.db), [])

    def test_no_server_state_is_idle(self):
        self.assertEqual(customize.busy_threads(self.db), [])

    def test_unreadable_state_counts_as_busy(self):
        self.db.write_text('not a database')
        self.assertEqual(len(customize.busy_threads(self.db)), 1)


class WaitUntilIdleTest(unittest.TestCase):
    def clock(self):
        now = [0]
        return now, (lambda: now[0]), (lambda seconds: now.__setitem__(0, now[0] + seconds))

    def test_waits_while_a_thread_works_then_returns(self):
        now, clock, sleep = self.clock()
        answers = [['Busy thread'], ['Busy thread'], []]
        with patch.object(customize, 'say'):
            customize.wait_until_idle('restart', timeout=600, poll=60, busy=lambda: answers.pop(0),
                                      sleep=sleep, clock=clock)
        self.assertEqual(now[0], 120)
        self.assertEqual(answers, [])

    def test_gives_up_without_restarting_after_the_timeout(self):
        now, clock, sleep = self.clock()
        with patch.object(customize, 'say'), self.assertRaises(customize.Deferred) as raised:
            customize.wait_until_idle('restart', timeout=600, poll=60, busy=lambda: ['Busy thread'],
                                      sleep=sleep, clock=clock)
        self.assertIn('deferred: threads busy', str(raised.exception))
        self.assertGreaterEqual(now[0], 600)


class UpdateT3ServerTest(unittest.TestCase):
    def test_skips_the_update_and_its_restart_when_already_newest(self):
        with patch.object(customize, 'server_runtime', return_value=('1.0-nightly', Path('/x'))), \
                patch.object(customize, 'latest_server_version', return_value='1.0-nightly'), \
                patch.object(customize, 'wait_until_idle') as gate, patch.object(customize.subprocess, 'run') as run, \
                patch.object(customize, 'say'):
            self.assertFalse(customize.update_t3_server())
        gate.assert_not_called()
        run.assert_not_called()

    def test_busy_threads_keep_t3_update_from_running(self):
        with patch.object(customize, 'server_runtime', return_value=('1.0-nightly', Path('/x'))), \
                patch.object(customize, 'latest_server_version', return_value='1.1-nightly'), \
                patch.object(customize, 'wait_until_idle', side_effect=customize.Deferred('busy')), \
                patch.object(customize.subprocess, 'run') as run:
            with self.assertRaises(customize.Deferred):
                customize.update_t3_server()
        run.assert_not_called()


class AcquireLockTest(unittest.TestCase):
    def test_waits_for_a_held_lock_and_names_the_holder(self):
        now = [0]
        calls = []

        def flock(lock, mode):
            calls.append(now[0])
            if now[0] < 60:
                raise BlockingIOError

        lines = []
        with tempfile.TemporaryFile('a+') as lock, patch('fcntl.flock', flock), \
                patch.object(customize, 'say', lines.append):
            lock.write('pid 1, t3code-customize ios, since 21:43:36\n')
            self.assertTrue(customize.acquire_lock(lock, wait=1800, sleep=lambda s: now.__setitem__(0, now[0] + s),
                                                   clock=lambda: now[0]))
        self.assertEqual(calls[-1], 60)
        self.assertIn('t3code-customize ios', lines[0])

    def test_gives_up_after_the_wait(self):
        now = [0]

        def flock(lock, mode):
            raise BlockingIOError

        with tempfile.TemporaryFile('a+') as lock, patch('fcntl.flock', flock), patch.object(customize, 'say'):
            self.assertFalse(customize.acquire_lock(lock, wait=1800, sleep=lambda s: now.__setitem__(0, now[0] + s),
                                                    clock=lambda: now[0]))
        self.assertGreaterEqual(now[0], 1800)


PATCH = '''From 0000000000000000000000000000000000000000 Mon Sep 17 00:00:00 2001
Subject: [PATCH 1/2] feat: thing

---
 a.ts | 2 ++
diff --git a/a.ts b/a.ts
index 1111111..2222222 100644
--- a/a.ts
+++ b/a.ts
@@ -{line},3 +{line},5 @@ {context}
 const before = 1;
+// {comment}
+const added = {value};
-const removed = 2;
 const after = 3;
'''


def patch_text(line=10, context='function f() {', comment='why', value=1):
    return PATCH.format(line=line, context=context, comment=comment, value=value)


class MergeDecisionTest(unittest.TestCase):
    def sets(self, text, extra=None):
        sets = {('patches-tt', '0001'): text}
        sets.update(extra or {})
        return sets

    def test_moved_context_and_comments_keep_the_code(self):
        before = self.sets(patch_text())
        after = self.sets(patch_text(line=42, context='function g() {', comment='reworded'))
        self.assertTrue(customize.code_unchanged(before, after))

    def test_a_changed_code_line_is_not_merged(self):
        self.assertFalse(customize.code_unchanged(self.sets(patch_text()), self.sets(patch_text(value=2))))

    def test_an_added_or_dropped_patch_is_not_merged(self):
        before = self.sets(patch_text())
        after = self.sets(patch_text(), {('patches-tt', '0002'): patch_text()})
        self.assertFalse(customize.code_unchanged(before, after))
        self.assertFalse(customize.code_unchanged(after, before))

    def test_reordered_hunks_count_as_the_same_code(self):
        swapped = patch_text().replace('+const added = 1;\n-const removed = 2;\n', '-const removed = 2;\n+const added = 1;\n')
        self.assertTrue(customize.code_unchanged(self.sets(patch_text()), self.sets(swapped)))

    def test_shared_patches_compare_against_patches_when_there_was_no_port(self):
        folders = {'patches': {'0001-a.patch': 'x', 'base.txt': 'b'}, 'patches-port': {}, 'patches-tt': {},
                   'patches-ios': {}}
        self.assertEqual(customize.patch_sets(folders.get), {('shared', '0001'): 'x'})

    def test_merges_only_when_checks_ran_and_code_is_unchanged(self):
        calls = []

        def repo_run(*args, check=True):
            calls.append(args[:3])
            return 'https://github.com/o/r/pull/9' if args[:3] == ('gh', 'pr', 'view') else ''

        for checked, code_same, merged in ((True, True, True), (True, False, False), (False, True, False)):
            calls.clear()
            with tempfile.TemporaryDirectory() as cache, \
                    patch.object(customize, 'CACHE', Path(cache)), \
                    patch.object(customize, 'patch_sets', return_value={}), \
                    patch.object(customize, 'code_unchanged', return_value=code_same), \
                    patch.object(customize, 'repo_run', repo_run), \
                    patch.object(customize.subprocess, 'run'), \
                    patch.object(customize.shutil, 'which', return_value='/usr/bin/gh'), \
                    patch.object(customize, 'spawn_detached') as spawn, \
                    patch.object(customize, 'REPO', ROOT):
                url, did_merge = customize._publish_port('1.0-nightly', checked=checked)
            self.assertEqual(url, 'https://github.com/o/r/pull/9')
            self.assertEqual(did_merge, merged)
            self.assertEqual(('gh', 'pr', 'merge') in calls, merged)
            self.assertEqual(spawn.called, merged)

    def test_a_port_made_by_hand_is_left_to_commit(self):
        with patch.object(customize, '_publish_port') as publish, patch.object(customize, 'say'):
            customize.publish_port(argparse.Namespace(skip_checks=False), '1.0-nightly')
        publish.assert_not_called()


class FleetCommandTest(unittest.TestCase):
    def args(self, **values):
        return argparse.Namespace(**{'fix': None, 'force': False, **values})

    def test_servers_update_t3_first_and_everyone_waits_for_the_lock(self):
        self.assertEqual(customize.fleet_command({'kind': 'server'}, self.args()),
                         ['server', '--no-pull', '--wait-lock', '30', '--t3-update'])
        self.assertEqual(customize.fleet_command({'kind': 'mac'}, self.args(fix='claude')),
                         ['update', '--no-pull', '--wait-lock', '30', '--fix', 'claude'])

    def test_autoupdate_uses_each_machines_own_settings(self):
        machines = {m['name']: m for m in customize.load(customize.MACHINES)['machines']}
        self.assertEqual(customize.autoupdate_command(machines['devbox1']), ['autoupdate', 'on', '--fix', 'claude'])
        self.assertEqual(customize.autoupdate_command(machines['mbp']), ['autoupdate', 'on', '--ios'])
        self.assertEqual(customize.autoupdate_command(machines['mba']), ['autoupdate', 'on'])


class IosAfterUpdateTest(unittest.TestCase):
    def test_ios_builds_only_when_the_nightly_changed(self):
        cases = (({'version': 'n2'}, {'version': 'n1'}, True), ({'version': 'n2'}, {'version': 'n2'}, False),
                 ({}, {'version': 'n1'}, False))
        for state, ios_state, expected in cases:
            with patch.object(customize, 'load', side_effect=lambda path, default=None:
                              state if path == customize.STATE else ios_state):
                self.assertEqual(customize.ios_behind_nightly(), expected)


if __name__ == '__main__':
    unittest.main()
