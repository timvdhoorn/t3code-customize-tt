import ast
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_recipe_hash', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

SCRIPT = ROOT / 't3code-customize'


def top_level_names(text):
    return {node.name for node in ast.parse(text).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def replace_in_function(text, name, old, new):
    """text with old replaced by new inside the top-level definition called name."""
    lines = text.splitlines(keepends=True)
    node = next(n for n in ast.parse(text).body if getattr(n, 'name', None) == name)
    body = ''.join(lines[node.lineno - 1:node.end_lineno])
    assert old in body, (name, old)
    lines[node.lineno - 1:node.end_lineno] = [body.replace(old, new, 1)]
    return ''.join(lines)


class OperationalCodeTest(unittest.TestCase):
    def test_every_denied_name_is_a_function_or_class_of_the_script(self):
        # A rename must not silently put the code back into the hash (or leave a stale name behind).
        self.assertEqual(set(customize.OPERATIONAL_CODE) - top_level_names(SCRIPT.read_text()), set())

    def test_no_build_function_is_denied(self):
        for name in ('apply_patches', 'build_server', 'build_bundles', 'build_web_and_server', 'checks',
                     'recipe_hash', 'build_source', 'overlay', 'assemble_mac', 'cmd_build', 'cmd_server',
                     'cmd_ios', 'build_ios', 'main', 'run_test_step', 'check_spec', 'repo_run', 'cmd_checks',
                     'follow_marker', 'recipe_for', 'extract_recipe', 'uncommitted_patches', 'server_runtime',
                     'server_installing'):
            self.assertIn(name, top_level_names(SCRIPT.read_text()))
            self.assertNotIn(name, customize.OPERATIONAL_CODE)


# Where the build starts. main is left out: it dispatches to every command.
BUILD_ROOTS = ('cmd_build', 'cmd_server', 'cmd_ios', 'cmd_update', 'apply_patches', 'cmd_verify', 'checks')

# Operational code the build entry points call, reviewed as unable to change what is built. A denied
# function that becomes reachable from the build and is not listed here fails the test: review it,
# then list it with its reason or take it out of OPERATIONAL_CODE.
REVIEWED_REACHED = {
    'PortHandedOff': 'exception that ends a run on the current build',
    'say': 'prints',
    'step': 'prints',
    'notify': 'sends a notification',
    'inside_t3_agent': 'decides where a server run executes, not what it builds',
    'release_checkout_lock': 'lock handling around a wait',
    'restart_lock': 'serialises swap and restart',
    'mark_staged': 'token that marks staged files as this run\'s',
    'still_newest': 'checks before the swap that this run\'s staged build is still the newest',
    'restart_owed': 'whether a restart is still pending',
    'restart_server': 'restarts the service after the files are swapped',
    'wait_until_idle': 'waits for idle threads before a restart',
    'stage_t3_update': 'fetches the newest T3 nightly; the build reads the version afterwards',
    'app_settled': 'waits for the app to be quiet before an update',
    'stuck_message': 'text of a stop message',
    'agent_prompt': 'prompt for the agent session; its result is patches, which are hashed',
    'choose_agent': 'picks which agent fixes a port; its result is patches, which are hashed',
    'hand_off_port': 'hands a port to the porter instead of building',
    'handed_off_already': 'skips a repeated hand-off',
    'port_failed': 'records a failed port',
    'port_pending': 'finds a published port for a nightly',
    'porter_machine': 'which machine ports',
    'publish_port': 'commits and opens the port PR',
}


class BuildReachTest(unittest.TestCase):
    def test_operational_code_reached_from_the_build_is_reviewed(self):
        defs = {node.name: node for node in ast.parse(SCRIPT.read_text()).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        seen, stack, reached = set(), list(BUILD_ROOTS), set()
        while stack:
            name = stack.pop()
            if name in seen or name not in defs:
                continue
            seen.add(name)
            if name in customize.OPERATIONAL_CODE:
                reached.add(name)
                continue  # not followed: its callees are only reached through it
            stack.extend(n.id for n in ast.walk(defs[name]) if isinstance(n, ast.Name) and n.id in defs)
        self.assertEqual(reached, set(REVIEWED_REACHED))


class BuildSourceTest(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text()
        self.base = customize.build_source(self.text)

    def test_a_denied_function_body_does_not_count(self):
        for name, old in (('notify', 'title'), ('wait_until_idle', 'timeout'), ('cmd_fleet', 'args'),
                          ('hand_off_port', 'problem'), ('restart_server', 'Restarting')):
            changed = replace_in_function(self.text, name, old, old + '_CHANGED')
            self.assertNotEqual(changed, self.text)
            self.assertEqual(customize.build_source(changed), self.base, name)

    def test_a_denied_function_added_or_removed_with_its_decorator_does_not_count(self):
        decorated = self.text + '\n\n@staticmethod\ndef notify_more():\n    return 1\n'
        self.assertNotEqual(customize.build_source(decorated), self.base)  # not denied: counts
        with patch.object(customize, 'OPERATIONAL_CODE', customize.OPERATIONAL_CODE | {'notify_more'}):
            self.assertEqual(customize.build_source(decorated), self.base)

    def test_whitespace_and_trailing_blanks_do_not_count(self):
        self.assertEqual(customize.build_source(self.text.replace('\n\n\n', '\n\n\n\n\n') + '   \n'), self.base)

    def test_a_build_function_counts(self):
        for name, old in (('apply_patches', 'target'), ('build_server', 'version'), ('checks', 'env'),
                          ('recipe_hash', 'digest')):
            changed = replace_in_function(self.text, name, old, old + '_CHANGED')
            self.assertNotEqual(customize.build_source(changed), self.base, name)

    def test_a_module_constant_counts(self):
        changed = self.text.replace("PNPM_INSTALL = ['--frozen-lockfile'", "PNPM_INSTALL = ['--changed', '--frozen-lockfile'", 1)
        self.assertNotEqual(changed, self.text)
        self.assertNotEqual(customize.build_source(changed), self.base)

    def test_a_new_function_counts(self):
        self.assertNotEqual(customize.build_source(self.text + '\n\ndef brand_new():\n    return 1\n'), self.base)

    def test_a_script_that_does_not_parse_counts_as_a_whole(self):
        self.assertEqual(customize.build_source('def broken(:\n'), 'def broken(:\n')


class RecipeHashTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        for folder in ('patches', 'patches-tt'):
            (self.repo / folder).mkdir()
        for name in ('checks.json', 'checks-tt.json', 'platform_support.py'):
            (self.repo / name).write_text(name)
        (self.repo / 'patches-tt/0001-a.patch').write_text('patch')
        self.script = self.repo / customize.NAME
        self.text = SCRIPT.read_text()
        self.write(self.text)
        self.ports = self.repo / 'ports.json'
        for name, value in (('REPO', self.repo), ('WITH_IOS', False), ('PORTS', self.ports)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, text):
        self.script.write_text(text)

    def test_operational_code_leaves_the_recipe_alone_and_the_full_hash_changes(self):
        before, full = customize.recipe_hash(), customize.recipe_hash(full=True)
        self.write(replace_in_function(self.text, 'cmd_fleet', 'args', 'args_CHANGED'))
        self.assertEqual(customize.recipe_hash(), before)
        self.assertNotEqual(customize.recipe_hash(full=True), full)

    def test_build_code_constants_and_patches_change_the_recipe(self):
        before = customize.recipe_hash()
        self.write(replace_in_function(self.text, 'apply_patches', 'target', 'target_CHANGED'))
        build_change = customize.recipe_hash()
        self.assertNotEqual(build_change, before)
        self.write(self.text.replace('PNPM_INSTALL = [', 'PNPM_INSTALL = ["--x", ', 1))
        self.assertNotEqual(customize.recipe_hash(), before)
        self.write(self.text)
        (self.repo / 'patches-tt/0001-a.patch').write_text('other patch')
        self.assertNotEqual(customize.recipe_hash(), before)

    def test_a_failed_port_is_retried_after_any_script_change(self):
        customize.save(self.ports, {'n2': {'failedEpoch': 1e12, 'failedRecipe': customize.recipe_hash(full=True)}})
        self.assertIsNotNone(customize.recent_failure('n2', clock=lambda: 1e12 + 60))
        # A fix to the port flow itself is operational code, yet it must retry the failed port.
        self.write(replace_in_function(self.text, 'hand_off_port', 'problem', 'problem_CHANGED'))
        self.assertIsNone(customize.recent_failure('n2', clock=lambda: 1e12 + 60))

    def test_a_handed_off_port_is_handed_again_after_any_script_change(self):
        handoffs = self.repo / 'handoffs.json'
        recipe = customize.recipe_hash(full=True)
        customize.save(handoffs, {'t': {'version': 'n', 'porter': 'p', 'at': 1e12, 'recipes': [recipe]}})
        with patch.object(customize, 'HANDOFFS', handoffs):
            with self.assertRaises(customize.PortHandedOff):
                customize.handed_off_already('t', 'n', clock=lambda: 1e12 + 60)
            self.write(replace_in_function(self.text, 'hand_off_port', 'problem', 'problem_CHANGED'))
            customize.handed_off_already('t', 'n', clock=lambda: 1e12 + 60)

    def test_ios_recipe_includes_the_ios_layer(self):
        (self.repo / 'patches-ios').mkdir()
        (self.repo / 'patches-ios/0001-i.patch').write_text('ios')
        self.assertNotEqual(customize.ios_recipe_hash(), customize.recipe_hash())


if __name__ == '__main__':
    unittest.main()
