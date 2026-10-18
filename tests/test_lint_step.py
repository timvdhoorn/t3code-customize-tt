import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_lint', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

IGNORED = 'apps/mobile/uniwind-types.d.ts'

# Stands in for `vp lint`: lists every file but IGNORED for --debug=files, and otherwise
# prints a JSON report as told by FAKE_LINT (ok, error, short, none, hang).
FAKE_VP = '''#!{python}
import json, os, subprocess, sys, time
args = sys.argv[2:]
files = [a for a in args if not a.startswith('-') and a != 'json']
with open(os.environ['FAKE_CALLS'], 'a') as calls:
    calls.write(json.dumps(args) + '\\n')
sys.stderr.write('note: You are running `vp lint` as a Vite+ built-in command.\\n')
mode = os.environ['FAKE_LINT']
if mode == 'hang':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    open(os.environ['FAKE_CHILD'], 'w').write(str(child.pid))
    time.sleep(60)
if '--debug=files' in args:
    if mode == 'foreign':
        print('apps/web/src/somewhere-else.ts')
    elif mode == 'absolute':
        print('\\n'.join(os.path.join(os.getcwd(), f) for f in files if f != {ignored!r}))
    else:
        print('\\n'.join(f for f in files if f != {ignored!r}))
    sys.exit(0)
if mode == 'none':
    print('No files found to lint. Please check your paths and ignore patterns.')
    sys.exit(0)
diagnostics = []
if mode == 'error':
    diagnostics.append(dict(message='Hermes does not implement Array#toSorted.', severity='error',
                            code='t3code(no-hermes-unsupported-apis)', filename=files[0],
                            labels=[dict(span=dict(line=1, column=39))]))
count = len(files) - (1 if mode == 'short' else 0)
print(json.dumps(dict(diagnostics=diagnostics, number_of_files=count)))
sys.exit(1 if diagnostics else 0)
'''


@unittest.skipIf(os.name == 'nt', 'the fake vp is a POSIX script')
class LintStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        vp = bin_dir / 'vp'
        vp.write_text(FAKE_VP.format(python=sys.executable, ignored=IGNORED))
        vp.chmod(0o755)
        self.calls = root / 'calls'
        self.child = root / 'child'
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        FAKE_CALLS=str(self.calls), FAKE_CHILD=str(self.child))
        self.log = (root / 'log').open('w+')
        self.addCleanup(self.log.close)
        patcher = patch.object(customize, 'SOURCE', root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def lint(self, mode, files, timeout=30):
        self.env['FAKE_LINT'] = mode
        customize.lint_changed(files, self.env, self.log, timeout=timeout)

    def lint_calls(self):
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return [c for c in calls if '--debug=files' not in c]

    def log_text(self):
        self.log.flush()
        self.log.seek(0)
        return self.log.read()

    def test_ignored_file_is_left_out_and_the_rest_is_linted(self):
        self.lint('ok', ['a.ts', IGNORED, 'b.tsx'])
        files = [a for a in self.lint_calls()[0] if not a.startswith('-') and a != 'json']
        self.assertEqual(files, ['a.ts', 'b.tsx'])
        self.assertIn('Lint ignores (ignorePatterns): ' + IGNORED, self.log_text())
        self.assertIn('Lint checked 2 of 3 changed files', self.log_text())

    def test_only_ignored_files_skip_the_lint(self):
        self.lint('ok', [IGNORED])
        self.assertEqual(self.lint_calls(), [])

    def test_error_diagnostic_fails_with_the_rule(self):
        with self.assertRaises(customize.NeedsFix) as stop:
            self.lint('error', ['apps/mobile/src/probe.ts'])
        self.assertIn('no-hermes-unsupported-apis', str(stop.exception))
        self.assertIn('apps/mobile/src/probe.ts:1:39', self.log_text())

    def test_fewer_files_linted_than_listed_fails(self):
        with self.assertRaises(customize.NeedsFix) as stop:
            self.lint('short', ['a.ts', 'b.ts'])
        self.assertIn('checked 1 files, expected 2', str(stop.exception))

    def test_no_report_fails_even_with_exit_zero(self):
        with self.assertRaises(customize.NeedsFix) as stop:
            self.lint('none', ['a.ts'])
        self.assertIn('No files found to lint', str(stop.exception))

    def test_a_listing_that_names_none_of_the_changed_files_fails(self):
        # A changed --debug=files format must not turn into linting nothing.
        with self.assertRaises(customize.NeedsFix) as stop:
            self.lint('foreign', ['a.ts', 'b.ts'])
        self.assertIn('none of the changed ones', str(stop.exception))
        self.assertEqual(self.lint_calls(), [])

    def test_absolute_paths_in_the_listing_match_the_changed_files(self):
        self.lint('absolute', ['a.ts', 'b.tsx'])
        files = [a for a in self.lint_calls()[0] if not a.startswith('-') and a != 'json']
        self.assertEqual(files, ['a.ts', 'b.tsx'])

    def test_hang_is_stopped_with_its_whole_process_tree(self):
        started = time.monotonic()
        with self.assertRaises(customize.NeedsFix) as stop:
            self.lint('hang', ['a.ts'], timeout=2)
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn('did not finish within 2 seconds', str(stop.exception))
        child = int(self.child.read_text())
        for _ in range(50):
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail('the lint child process survived the timeout')


if __name__ == '__main__':
    unittest.main()
