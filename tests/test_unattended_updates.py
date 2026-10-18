import argparse
import contextlib
import json
import importlib.machinery
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_unattended', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


def state_db(path, runs, provider_threads=()):
    """A statev2.sqlite with the projection tables the idle check reads."""
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE orchestration_v2_projection_threads (thread_id TEXT PRIMARY KEY, title TEXT,'
               ' deleted_at TEXT)')
    db.execute('CREATE TABLE orchestration_v2_projection_runs (run_id TEXT PRIMARY KEY, thread_id TEXT,'
               ' status TEXT, payload_json TEXT)')
    db.execute('CREATE TABLE orchestration_v2_projection_provider_threads (provider_thread_id TEXT PRIMARY KEY,'
               ' thread_id TEXT, status TEXT, payload_json TEXT)')
    for index, (title, status, deleted, *payload) in enumerate(runs):
        db.execute('INSERT INTO orchestration_v2_projection_threads VALUES (?, ?, ?)',
                   (f't{index}', title, '2026-10-16' if deleted else None))
        db.execute('INSERT INTO orchestration_v2_projection_runs VALUES (?, ?, ?, ?)',
                   (f'r{index}', f't{index}', status, json.dumps(payload[0] if payload else {})))
    for index, (thread, payload) in enumerate(provider_threads):
        db.execute('INSERT INTO orchestration_v2_projection_provider_threads VALUES (?, ?, ?, ?)',
                   (f'p{index}', thread, 'idle', json.dumps(payload)))
    db.commit()
    db.close()


class BusyThreadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'statev2.sqlite'

    def test_every_live_run_status_counts_as_busy(self):
        statuses = customize.LIVE_RUN_STATUSES + ('queued',)
        state_db(self.db, [(status, status, False) for status in statuses])
        self.assertEqual(customize.busy_threads(self.db), sorted(statuses))

    def test_finished_runs_held_queues_and_deleted_threads_are_idle(self):
        state_db(self.db, [('done', 'completed', False), ('stopped', 'interrupted', False),
                           ('failed', 'failed', False), ('gone', 'running', True),
                           ('held', 'queued', False, {'queueHeld': True})])
        self.assertEqual(customize.busy_threads(self.db), [])

    def test_pending_background_tasks_count_as_busy(self):
        state_db(self.db, [('background', 'completed', False), ('quiet', 'completed', False)],
                 provider_threads=[('t0', {'pendingBackgroundTasks': [{'id': 'b1'}]}),
                                   ('t1', {'pendingBackgroundTasks': []})])
        self.assertEqual(customize.busy_threads(self.db), ['background'])

    def test_no_state_is_idle_only_without_a_server(self):
        self.assertEqual(customize.busy_threads(self.db, server=False), [])
        self.assertEqual(len(customize.busy_threads(self.db, server=True)), 1)
        with patch.object(customize, 'server_runtime', return_value=('1.0-nightly', Path('/x'))):
            self.assertEqual(len(customize.busy_threads(self.db)), 1)

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


class StageT3UpdateTest(unittest.TestCase):
    def test_t3_update_stages_without_yes_or_a_terminal(self):
        runtimes = [('1.0-nightly', Path('/x')), ('1.1-nightly', Path('/y'))]
        with patch.object(customize, 'server_runtime', side_effect=runtimes), \
                patch.object(customize.subprocess, 'run') as run, patch.object(customize, 'say'), \
                patch.object(customize, 'step'):
            run.return_value.returncode = 0
            self.assertTrue(customize.stage_t3_update())
        argv = run.call_args.args[0]
        self.assertEqual(argv, ['/x/t3', 'update'])
        self.assertIs(run.call_args.kwargs['stdin'], customize.subprocess.DEVNULL)

    def test_reports_no_change_when_already_newest(self):
        with patch.object(customize, 'server_runtime', return_value=('1.0-nightly', Path('/x'))), \
                patch.object(customize.subprocess, 'run') as run, patch.object(customize, 'say'), \
                patch.object(customize, 'step'):
            run.return_value.returncode = 0
            self.assertFalse(customize.stage_t3_update())


class RestartTest(unittest.TestCase):
    def test_a_thread_that_starts_just_before_the_restart_defers_it(self):
        with patch.object(customize, 'systemctl') as systemctl, self.assertRaises(customize.Deferred):
            customize.restart_service('restart', busy=lambda: ['New thread'])
        self.assertNotIn(('restart', customize.SERVICE_UNIT), [c.args for c in systemctl.call_args_list])

    def test_idle_restarts_after_reloading_the_unit(self):
        with patch.object(customize, 'systemctl') as systemctl:
            customize.restart_service('restart', busy=lambda: [])
        self.assertEqual([c.args for c in systemctl.call_args_list],
                         [('daemon-reload',), ('restart', customize.SERVICE_UNIT)])

    def test_rollback_does_not_restart_a_server_that_threads_use(self):
        restarts = []
        with patch.object(customize, 'restart_service'), patch.object(customize, 'server_healthy', return_value=False), \
                patch.object(customize, 'restore_server_stock') as restore, \
                patch.object(customize, 'systemctl', side_effect=lambda *a: restarts.append(a) or
                             argparse.Namespace(returncode=0)), \
                patch.object(customize, 'busy_threads', return_value=['Busy']), \
                patch.object(customize, 'say'), patch.object(customize, 'step'), self.assertRaises(customize.Stop):
            customize.restart_server(Path('/x'))
        restore.assert_called_once()
        self.assertNotIn(('restart', customize.SERVICE_UNIT), restarts)


class OwedRestartTest(unittest.TestCase):
    """A restart deferred after the files were swapped must happen on the next run."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runtime = Path(tmp.name)
        for name, value in (('OWED_RESTART', self.runtime / '.owed'), ('T3_RESTART_PENDING', self.runtime / '.rp'),
                            ('RESTART_LOCK', self.runtime / 'restart-lock')):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_server(self, mark_version='1.1-nightly'):
        args = argparse.Namespace(no_restart=False, no_pull=True, resume=False, t3_update=False, force=False)
        with patch.object(customize, 'MAC', False), patch.object(customize, 'inside_t3_service', return_value=False), \
                patch.object(customize, 'server_runtime', return_value=('1.1-nightly', self.runtime)), \
                patch.object(customize, 'server_installing', return_value=False), \
                patch.object(customize, 'recipe_hash', return_value='r'), \
                patch.object(customize, 'load', return_value={'version': mark_version, 'recipe': 'r'}), \
                patch.object(customize, 'wait_until_idle') as gate, \
                patch.object(customize, 'restart_server') as restart, patch.object(customize, 'say'):
            customize.cmd_server(args)
        return gate, restart

    def test_up_to_date_without_an_owed_restart_does_nothing(self):
        gate, restart = self.run_server()
        restart.assert_not_called()

    def test_a_deferred_restart_is_retried_when_the_build_is_already_installed(self):
        customize.OWED_RESTART.write_text('x')
        gate, restart = self.run_server()
        gate.assert_called_once()
        restart.assert_called_once()

    def test_a_version_t3_update_staged_is_restarted_onto(self):
        customize.T3_RESTART_PENDING.write_text('1.1-nightly\n')
        self.assertTrue(customize.restart_owed('1.1-nightly'))
        # A marker for another version is not cleared by a restart, so it does not count.
        self.assertFalse(customize.restart_owed('1.2-nightly'))

    def test_the_owed_restart_stays_until_a_restart_happened(self):
        with patch.object(customize, 'restart_service', side_effect=customize.Deferred('busy')), \
                patch.object(customize, 'step'), self.assertRaises(customize.Deferred):
            customize.restart_server(self.runtime)
        self.assertTrue(customize.OWED_RESTART.exists())
        with patch.object(customize, 'restart_service'), patch.object(customize, 'server_healthy', return_value=True), \
                patch.object(customize, 'step'):
            customize.restart_server(self.runtime)
        self.assertFalse(customize.OWED_RESTART.exists())


STAGE_SERVER_BUILD = customize.stage_server_build


class ServerRunLockTest(unittest.TestCase):
    """A server run holds the checkout lock only while it uses the checkout, and of two runs that
    wait for idle threads at once only the newest staged build is swapped in."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / 'versions/1.1-nightly'
        (self.folder / 'client').mkdir(parents=True)
        (self.folder / 'client/index.js').write_text('')
        (self.folder / 't3').write_text('stock')
        self.checkout_lock = self.root / 'lock'
        self.runtime = ('1.1-nightly', self.folder)
        self.installed = []
        for name, value in (('CACHE', self.root / 'cache'), ('RESTART_LOCK', self.root / 'restart-lock'),
                            ('OWED_RESTART', self.root / '.owed'), ('T3_RESTART_PENDING', self.root / '.rp'),
                            ('MAC', False)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def checkout_lock_free(self):
        return self.lock_free(self.checkout_lock)

    def stage(self, folder, version):
        (folder / 't3.customize-new').write_text('customized')
        (folder / 'client.customize-new').mkdir(exist_ok=True)
        return customize.mark_staged(folder, version)

    def lock_free(self, path):
        import fcntl
        with path.open('a+') as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            fcntl.flock(other, fcntl.LOCK_UN)
            return True

    def run_server(self, gate=lambda action: None, recipe='r', ported=False, restart=None):
        """One cmd_server with a fresh build, holding the checkout lock as main() does. recipe=None
        keeps the real recipe_hash."""
        import fcntl
        args = argparse.Namespace(no_restart=False, no_pull=True, resume=False, t3_update=False, force=False)
        lock = self.checkout_lock.open('a+')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        customize.CHECKOUT_LOCK = lock
        self.addCleanup(setattr, customize, 'CHECKOUT_LOCK', None)
        recipes = patch.object(customize, 'recipe_hash', return_value=recipe) if recipe else contextlib.nullcontext()
        with patch.object(customize, 'inside_t3_service', return_value=False), \
                patch.object(customize, 'server_runtime', side_effect=lambda: self.runtime), \
                patch.object(customize, 'server_installing', return_value=False), recipes, \
                patch.object(customize, 'public_config_from', return_value=dict(customize.PUBLIC_CONFIG)), \
                patch.object(customize, 'ensure_node'), patch.object(customize, 'build_env', return_value={}), \
                patch.object(customize, 'ensure_commit', return_value='abc'), \
                patch.object(customize, 'apply_patches', return_value=ported), \
                patch.object(customize, 'export_patches'), patch.object(customize, 'publish_port'), \
                patch.object(customize, 'git', return_value='head'), \
                patch.object(customize, 'build_rewrites_discarded', contextlib.nullcontext), \
                patch.object(customize, 'build_server'), \
                patch.object(customize, 'stage_server_build', side_effect=self.stage), \
                patch.object(customize, 'wait_until_idle', side_effect=gate), \
                patch.object(customize, 'install_server_build',
                             side_effect=lambda folder, version, commit, recipe: self.installed.append(recipe)
                             or (folder / customize.STAGED_MARK).unlink()), \
                patch.object(customize, 'restart_server', side_effect=restart) as restart, \
                patch.object(customize, 'say'), patch.object(customize, 'step'):
            result = customize.cmd_server(args)
        return result, restart

    def test_a_port_can_take_the_checkout_lock_while_the_server_run_waits_for_idle(self):
        free = []
        result, restart = self.run_server(gate=lambda action: free.append(self.checkout_lock_free()))
        self.assertEqual(free, [True])
        self.assertTrue(result)
        self.assertEqual(self.installed, ['r'])
        restart.assert_called_once()

    def test_the_restart_lock_is_free_while_the_server_run_waits_for_idle(self):
        free = []
        self.run_server(gate=lambda action: free.append(self.lock_free(customize.RESTART_LOCK)))
        self.assertEqual(free, [True])

    def test_the_recorded_recipe_is_the_one_built_even_if_a_port_changes_the_patches_meanwhile(self):
        repo = self.root / 'repo'
        for folder in ('patches', 'patches-tt'):
            (repo / folder).mkdir(parents=True)
        for name in ('checks.json', 'checks-tt.json', customize.NAME, 'platform_support.py'):
            (repo / name).write_text(name)
        (repo / 'patches-tt/0001-a.patch').write_text('ported')
        with patch.object(customize, 'REPO', repo), patch.object(customize, 'WITH_IOS', False):
            built = customize.recipe_hash()

            def gate(action):
                # A port that got the checkout lock during the wait commits newer patches.
                (repo / 'patches-tt/0002-b.patch').write_text('newer port')

            self.run_server(gate=gate, recipe=None, ported=True)
            self.assertNotEqual(customize.recipe_hash(), built)
        self.assertEqual(self.installed, [built])

    def test_a_deferred_restart_in_the_swap_releases_the_restart_lock_and_leaves_the_owed_marker(self):
        def deferred(folder, action):
            customize.OWED_RESTART.write_text('x')
            raise customize.Deferred('busy')

        with self.assertRaises(customize.Deferred):
            self.run_server(restart=deferred)
        self.assertEqual(self.installed, ['r'])
        self.assertTrue(self.lock_free(customize.RESTART_LOCK))
        self.assertTrue(customize.OWED_RESTART.exists())

    def real_stage(self, version='1.1-nightly', probe_ok=True, copy_fails=False):
        """stage_server_build itself, from a fake build in a fake checkout."""
        source = self.root / 'source'
        (source / 'apps/server/dist-exe').mkdir(parents=True, exist_ok=True)
        (source / 'apps/server/dist/client').mkdir(parents=True, exist_ok=True)
        (source / 'apps/server/dist-exe/t3').write_text('newer build')
        probe = argparse.Namespace(returncode=0 if probe_ok else 1, stdout=version if probe_ok else '', stderr='crash')

        def copytree(*args, **kwargs):
            raise OSError('disk full')

        with patch.object(customize, 'SOURCE', source), patch.object(customize.subprocess, 'run', return_value=probe), \
                patch.object(customize.shutil, 'copytree', copytree) if copy_fails else contextlib.nullcontext(), \
                customize.restart_lock():
            # The real one, also while run_server has patched it for the waiting run.
            return STAGE_SERVER_BUILD(self.folder, version)

    def test_a_waiter_does_not_install_files_a_newer_run_failed_to_stage(self):
        result, restart = self.run_server(gate=lambda action: self.assertRaises(customize.Stop, self.real_stage,
                                                                                 probe_ok=False))
        self.assertFalse(result)
        restart.assert_not_called()
        self.assertEqual(self.installed, [])

    def test_a_waiter_does_not_install_files_a_newer_run_copied_only_half(self):
        result, restart = self.run_server(gate=lambda action: self.assertRaises(OSError, self.real_stage,
                                                                                 copy_fails=True))
        self.assertFalse(result)
        restart.assert_not_called()
        self.assertEqual(self.installed, [])
        # The half-copied binary is there, but nothing marks it as anyone's to install.
        self.assertEqual((self.folder / 't3.customize-new').read_text(), 'newer build')
        self.assertFalse((self.folder / customize.STAGED_MARK).exists())

    def test_a_staged_build_is_marked_only_once_its_probe_passed(self):
        token = self.real_stage()
        self.assertEqual(customize.load(self.folder / customize.STAGED_MARK, {}).get('token'), token)
        with self.assertRaises(customize.Stop):
            self.real_stage(probe_ok=False)
        self.assertFalse((self.folder / customize.STAGED_MARK).exists())

    def test_yield_messages_name_the_actual_cause(self):
        cases = []
        with patch.object(customize, 'say', cases.append):
            token = self.stage(self.folder, '1.1-nightly')
            with patch.object(customize, 'server_runtime', return_value=None):
                self.assertFalse(customize.still_newest(self.folder, '1.1-nightly', token))
            token = self.stage(self.folder, '1.1-nightly')
            with patch.object(customize, 'server_runtime', return_value=self.runtime):
                customize.discard_staged(self.folder)
                self.assertFalse(customize.still_newest(self.folder, '1.1-nightly', token))
                self.stage(self.folder, '1.1-nightly')
                self.assertFalse(customize.still_newest(self.folder, '1.1-nightly', token))
        self.assertIn('Could not read the service state', cases[0])
        self.assertIn('server-off or a failed run', cases[1])
        self.assertIn('A newer run staged', cases[2])

    def test_the_checkout_lock_is_held_while_the_build_runs(self):
        held = []
        original = self.stage
        # Staging copies the build out of the checkout, the last step that reads it.
        self.stage = lambda folder, version: held.append(not self.checkout_lock_free()) or original(folder, version)
        self.run_server()
        self.assertEqual(held, [True])

    def test_of_two_waiters_only_the_newest_staged_build_is_swapped_in(self):
        newer = []

        def gate(action):
            # While the older run waits for idle, a newer one builds, stages, waits and swaps.
            if not newer:
                newer.append(self.run_server(recipe='newer'))

        result, restart = self.run_server(gate=gate, recipe='older')
        self.assertFalse(result)
        restart.assert_not_called()
        self.assertTrue(newer[0][0])
        self.assertEqual(self.installed, ['newer'])

    def test_an_older_waiter_yields_to_a_build_staged_over_it(self):
        def gate(action):
            customize.mark_staged(self.folder, '1.1-nightly')

        result, restart = self.run_server(gate=gate)
        self.assertFalse(result)
        restart.assert_not_called()
        self.assertEqual(self.installed, [])

    def test_a_waiter_yields_and_cleans_up_when_t3_moved_to_another_version(self):
        other = self.root / 'versions/1.2-nightly'
        other.mkdir(parents=True)

        def gate(action):
            self.runtime = ('1.2-nightly', other)

        result, restart = self.run_server(gate=gate)
        self.assertFalse(result)
        restart.assert_not_called()
        self.assertEqual(self.installed, [])
        self.assertFalse((self.folder / 't3.customize-new').exists())
        self.assertFalse((self.folder / customize.STAGED_MARK).exists())

    def test_server_off_drops_a_staged_build_so_a_waiter_cannot_swap_it_in(self):
        self.stage(self.folder, '1.1-nightly')
        token = customize.mark_staged(self.folder, '1.1-nightly')
        args = argparse.Namespace(no_restart=True)
        with patch.object(customize, 'server_runtime', return_value=self.runtime), \
                patch.object(customize, 'restore_server_stock'), patch.object(customize, 'say'):
            customize.cmd_server_off(args)
            self.assertFalse(customize.still_newest(self.folder, '1.1-nightly', token))
        self.assertFalse((self.folder / 't3.customize-new').exists())

    def test_the_owed_restart_waits_for_idle_without_the_checkout_lock(self):
        import fcntl
        customize.OWED_RESTART.write_text('x')
        lock = self.checkout_lock.open('a+')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        customize.CHECKOUT_LOCK = lock
        self.addCleanup(setattr, customize, 'CHECKOUT_LOCK', None)
        free = []
        args = argparse.Namespace(no_restart=False, no_pull=True, resume=False, t3_update=False, force=False)
        with patch.object(customize, 'inside_t3_service', return_value=False), \
                patch.object(customize, 'server_runtime', return_value=self.runtime), \
                patch.object(customize, 'server_installing', return_value=False), \
                patch.object(customize, 'recipe_hash', return_value='r'), \
                patch.object(customize, 'load', return_value={'version': '1.1-nightly', 'recipe': 'r'}), \
                patch.object(customize, 'wait_until_idle', side_effect=lambda a: free.append(self.checkout_lock_free())), \
                patch.object(customize, 'restart_server') as restart, patch.object(customize, 'say'):
            customize.cmd_server(args)
        self.assertEqual(free, [True])
        restart.assert_called_once()


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

SECOND_FILE = '''diff --git a/b.ts b/b.ts
index 3333333..4444444 100644
--- a/b.ts
+++ b/b.ts
@@ -1,1 +1,2 @@
 keep();
+other();
'''


def patch_text(line=10, context='function f() {', comment='why', value=1):
    return PATCH.format(line=line, context=context, comment=comment, value=value)


class MergeDecisionTest(unittest.TestCase):
    def sets(self, text, extra=None):
        sets = {('patches-tt', '0001'): text}
        sets.update(extra or {})
        return sets

    def same(self, before, after):
        return customize.code_unchanged(self.sets(before), self.sets(after))

    def test_moved_context_and_comments_keep_the_code(self):
        self.assertTrue(self.same(patch_text(), patch_text(line=42, context='function g() {', comment='reworded')))

    def test_a_changed_code_line_is_not_merged(self):
        self.assertFalse(self.same(patch_text(), patch_text(value=2)))

    def test_an_added_or_dropped_patch_is_not_merged(self):
        before = self.sets(patch_text())
        after = self.sets(patch_text(), {('patches-tt', '0002'): patch_text()})
        self.assertFalse(customize.code_unchanged(before, after))
        self.assertFalse(customize.code_unchanged(after, before))

    def test_reordered_lines_or_files_are_not_merged(self):
        swapped = patch_text().replace('+const added = 1;\n-const removed = 2;\n', '-const removed = 2;\n+const added = 1;\n')
        self.assertFalse(self.same(patch_text(), swapped))
        self.assertFalse(self.same(patch_text() + SECOND_FILE, SECOND_FILE + patch_text()))
        # The same lines moved to another file are another change.
        self.assertFalse(self.same(patch_text(), patch_text().replace('a.ts', 'c.ts')))

    def test_hash_lines_are_code(self):
        self.assertFalse(self.same(patch_text(comment='x'), patch_text(comment='x').replace('+// x', '+#private = 1;')))

    def test_code_lines_starting_with_plus_plus_or_minus_minus_count(self):
        before = patch_text().replace('+const added = 1;', '++count;')
        self.assertIn('++count;', [line for _, lines in customize.code_lines(before) for line in lines])
        self.assertFalse(self.same(before, patch_text().replace('+const added = 1;', '+--count;')))

    def test_code_after_a_closed_comment_counts(self):
        self.assertFalse(self.same(patch_text(comment='x'), patch_text(comment='x').replace('+// x', '+/* x */ run();')))
        self.assertTrue(self.same(patch_text(comment='x').replace('+// x', '+/** x */'),
                                  patch_text(comment='x').replace('+// x', '+/* y */')))

    def test_star_lines_are_comments_only_inside_a_block(self):
        block = patch_text(comment='x').replace('+// x', '+/**\n+ * x\n+ */')
        reworded = patch_text(comment='x').replace('+// x', '+/**\n+ * y\n+ */')
        self.assertTrue(self.same(block, reworded))
        self.assertFalse(self.same(patch_text(comment='x'), patch_text(comment='x').replace('+// x', '+* ptr;')))

    def test_binary_or_mode_changes_are_not_merged(self):
        binary = patch_text() + 'diff --git a/i.png b/i.png\nindex 1..2 100644\nGIT binary patch\nliteral 1\n'
        mode = patch_text() + 'diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n'
        self.assertFalse(self.same(binary, binary))
        self.assertFalse(self.same(mode, mode))

    def test_shared_patches_compare_against_patches_when_there_was_no_port(self):
        folders = {'patches': {'0001-a.patch': 'x', 'base.txt': 'b'}, 'patches-port': {}, 'patches-tt': {},
                   'patches-ios': {}}
        self.assertEqual(customize.patch_sets(folders.get), {('shared', '0001'): 'x'})

    def test_merges_only_when_checks_ran_and_code_is_unchanged(self):
        calls = []

        def repo_run(*args, check=True):
            calls.append(args[:3])
            return 'https://github.com/o/r/pull/9' if args[:3] == ('gh', 'pr', 'view') else ''

        cases = ((True, True, [], True), (True, False, [], False), (False, True, [], False),
                 (True, True, ['checks-tt.json'], False), (True, True, ['t3code-customize'], False))
        for checked, code_same, other, merged in cases:
            calls.clear()
            with tempfile.TemporaryDirectory() as cache, \
                    patch.object(customize, 'CACHE', Path(cache)), \
                    patch.object(customize, 'patch_sets', return_value={}), \
                    patch.object(customize, 'port_changes', return_value=(['patches-tt/0001-a.patch'], other)), \
                    patch.object(customize, 'port_branch', return_value='port/nightly-1.0-nightly'), \
                    patch.object(customize, 'code_unchanged', return_value=code_same), \
                    patch.object(customize, 'repo_run', repo_run), \
                    patch.object(customize.subprocess, 'run') as run, \
                    patch.object(customize.shutil, 'copy2'), \
                    patch.object(customize.shutil, 'which', return_value='/usr/bin/gh'), \
                    patch.object(customize, 'spawn_detached') as spawn, \
                    patch.object(customize, 'REPO', Path(cache)):
                for path in ['.git/HEAD', 'patches-tt/0001-a.patch'] + other:
                    (Path(cache) / path).parent.mkdir(parents=True, exist_ok=True)
                    (Path(cache) / path).write_text('x')
                url, did_merge = customize._publish_port('1.0-nightly', checked=checked)
            self.assertEqual(url, 'https://github.com/o/r/pull/9')
            self.assertEqual(did_merge, merged, (checked, code_same, other))
            self.assertEqual(('gh', 'pr', 'merge') in calls, merged)
            self.assertEqual(spawn.called, merged)
            staged = [c.args[0][-1] for c in run.call_args_list if c.args[0][:2] == ['git', 'add']]
            self.assertEqual(staged, ['patches-tt/0001-a.patch'] + [p for p in other if p in customize.CHECK_FILES])
            if merged:
                self.assertIn('--wait-lock', spawn.call_args.args[0])

    def test_untracked_files_outside_the_patch_folders_do_not_block_a_merge(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
            git('init', '-q')
            (Path(repo) / 'patches-tt').mkdir()
            (Path(repo) / 'patches-tt/0001-a.patch').write_text('a')
            (Path(repo) / 'checks-tt.json').write_text('[]')
            git('add', '.')
            git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init')
            (Path(repo) / 'patches-tt/0001-a.patch').write_text('b')
            (Path(repo) / 'patches-tt/0002-b.patch').write_text('new')
            (Path(repo) / 'patches-tt/.syncthing.0002-b.patch.tmp').write_text('tmp')
            (Path(repo) / 'skills-lock.json').write_text('{}')
            (Path(repo) / '.agents/skills/x').mkdir(parents=True)
            (Path(repo) / '.agents/skills/x/SKILL.md').write_text('x')
            with patch.object(customize, 'REPO', Path(repo)):
                self.assertEqual(customize.port_changes(),
                                 (['patches-tt/0001-a.patch', 'patches-tt/0002-b.patch'], []))
                (Path(repo) / 'checks-tt.json').write_text('["x"]')
                (Path(repo) / 'patches-tt/notes.md').write_text('n')
                self.assertEqual(customize.port_changes()[1], ['checks-tt.json', 'patches-tt/notes.md'])

    def test_a_merge_the_repo_cannot_follow_says_it_merged(self):
        notes = []
        with patch.object(customize, '_publish_port', side_effect=customize.MergedButStuck('pull/9 is merged, but')), \
                patch.object(customize, 'notify', lambda title, text: notes.append(text)):
            customize.publish_port(argparse.Namespace(agent_ported=True, skip_checks=False), '1.0-nightly')
        self.assertIn('is merged', notes[0])
        self.assertNotIn('opening the PR failed', notes[0])

    def test_only_patch_files_are_port_files(self):
        self.assertTrue(customize.is_port_file('patches-tt/0001-a.patch'))
        self.assertTrue(customize.is_port_file('patches-port/base.txt'))
        for path in ('patches-tt/.syncthing.0001-a.patch.tmp', 'patches-tt/notes.md', 'checks-tt.json', 'x/0001.patch'):
            self.assertFalse(customize.is_port_file(path) and '.syncthing.' not in path, path)

    def test_a_branch_with_someone_elses_commits_gets_a_fresh_name(self):
        def repo_run(*args, check=True):
            if args[:2] == ('git', 'ls-remote'):
                return 'sha\trefs/heads/x' if args[-1] == 'port/nightly-1' else ''
            if args[:2] == ('git', 'log'):
                return 'fix: by hand'
            return ''
        with patch.object(customize, 'repo_run', repo_run):
            self.assertEqual(customize.port_branch('1', 'chore: port patches to nightly 1'), 'port/nightly-1-2')

    def test_the_tools_own_branch_is_reused(self):
        def repo_run(*args, check=True):
            if args[:2] == ('git', 'ls-remote'):
                return 'sha\trefs/heads/x'
            return 'chore: port patches to nightly 1' if args[:2] == ('git', 'log') else ''
        with patch.object(customize, 'repo_run', repo_run):
            self.assertEqual(customize.port_branch('1', 'chore: port patches to nightly 1'), 'port/nightly-1')

    def test_a_port_made_by_hand_is_left_to_commit(self):
        with patch.object(customize, '_publish_port') as publish, patch.object(customize, 'say'):
            customize.publish_port(argparse.Namespace(skip_checks=False), '1.0-nightly')
        publish.assert_not_called()


class FleetCommandTest(unittest.TestCase):
    def args(self, **values):
        return argparse.Namespace(**{'fix': None, 'force': False, **values})

    def test_servers_update_t3_first_and_everyone_waits_for_the_lock(self):
        self.assertEqual(customize.fleet_command({'kind': 'server'}, self.args(wait_lock=30)),
                         ['server', '--no-pull', '--wait-lock', '30', '--t3-update'])
        self.assertEqual(customize.fleet_command({'kind': 'mac'}, self.args(fix='claude', wait_lock=180)),
                         ['update', '--no-pull', '--wait-lock', '180', '--fix', 'claude'])

    def test_autoupdate_uses_each_machines_own_settings(self):
        machines = {m['name']: m for m in customize.load(customize.MACHINES)['machines']}
        # devbox1 is the porter (16 cores, idle); the MacBook Pro builds iOS and hands ports over.
        self.assertEqual(customize.autoupdate_command(machines['devbox1']), ['autoupdate', 'on', '--fix', 'claude'])
        self.assertEqual(customize.autoupdate_command(machines['mbp']), ['autoupdate', 'on', '--ios'])
        self.assertEqual(customize.porter_machine(list(machines.values()))['name'], 'devbox1')
        self.assertEqual(customize.autoupdate_command(machines['mba']), ['autoupdate', 'on'])


class IosAfterUpdateTest(unittest.TestCase):
    def test_ios_builds_only_when_the_nightly_changed(self):
        cases = (({'version': 'n2'}, {'version': 'n1'}, True), ({'version': 'n2'}, {'version': 'n2'}, False),
                 ({}, {'version': 'n1'}, False))
        for state, ios_state, expected in cases:
            with patch.object(customize, 'load', side_effect=lambda path, default=None:
                              state if path == customize.STATE else ios_state):
                self.assertEqual(customize.ios_behind_nightly(), expected)

    def test_a_build_that_fails_before_the_upload_is_tried_again(self):
        saved = []
        with patch.object(customize, 'ios_behind_nightly', return_value=True), \
                patch.object(customize, 'load', side_effect=lambda path, default=None:
                             {} if path == customize.IOS_ATTEMPT else {'version': 'n2'}), \
                patch.object(customize, 'save', lambda path, value: saved.append(path)), \
                patch.object(customize, 'cmd_ios', side_effect=customize.Stop('xcodebuild failed')) as ios, \
                patch.object(customize, 'notify'):
            customize.update_ios(argparse.Namespace(app=None, fix=None))
        self.assertEqual(saved, [])
        self.assertIs(ios.call_args.args[0].attempt, customize.IOS_ATTEMPT)


if __name__ == '__main__':
    unittest.main()
