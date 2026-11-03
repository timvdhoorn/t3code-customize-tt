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
loader = importlib.machinery.SourceFileLoader('customize_known_failures', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

FILE = 'apps/web/src/Timeline.browser.test.tsx'
KNOWN = 'Timeline rows > keeps the heading in place'
OTHER = 'Timeline rows > renders a row'
UPSTREAM = '''import { describe, expect, it } from "vitest";

describe("Timeline rows", () => {
  it("keeps the heading in place", async () => {
    expect(577).toBeCloseTo(473);
  });

  it("renders a row", () => {
    expect(1).toBe(1);
  });
});
'''

# Stands in for `vp test run`: writes the JSON report FAKE_REPORT names (or garbage) and exits FAKE_CODE.
FAKE_VP = '''#!{python}
import os, sys
out = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--outputFile.json='))
open(out, 'w').write(open(os.environ['FAKE_REPORT']).read())
print(os.environ.get('FAKE_OUTPUT', ''))
sys.exit(int(os.environ['FAKE_CODE']))
'''


def assertion(full, status):
    *ancestors, title = full.split(' > ')
    return {'ancestorTitles': ancestors, 'title': title, 'fullName': ' '.join(full.split(' > ')),
            'status': status, 'failureMessages': ['AssertionError: expected 577 to be close to 473']
            if status == 'failed' else []}


def report(results, name=FILE, message=''):
    return {'testResults': [{'name': str(customize.SOURCE / name), 'status': 'failed'
                             if any(s == 'failed' for _, s in results) else 'passed', 'message': message,
                             'assertionResults': [assertion(f, s) for f, s in results]}]}


class KnownFailuresTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.source = base / 't3code'
        self.source.mkdir()
        (self.source / FILE).parent.mkdir(parents=True)
        (self.source / FILE).write_text(UPSTREAM)
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
                   GIT_COMMITTER_EMAIL='t@t')
        for args in (['init', '-q'], ['add', '-A'], ['commit', '-qm', 'nightly']):
            subprocess.run(['git', *args], cwd=self.source, check=True, env=env)
        self.target = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=self.source, check=True,
                                     capture_output=True, text=True).stdout.strip()
        self.known = base / 'known-upstream-failures.json'
        self.known.write_text(json.dumps({'failures': [
            {'file': FILE, 'test': KNOWN, 'upstream': 'https://example.invalid/pr/1', 'added': '2026-11-03'}]}))
        self.seen = base / 'seen.json'
        self.bin = base / 'bin'
        self.bin.mkdir()
        (self.bin / 'vp').write_text(FAKE_VP.format(python=sys.executable))
        (self.bin / 'vp').chmod(0o755)
        self.report = base / 'report.json'
        for name, value in (('SOURCE', self.source), ('KNOWN_FAILURES', self.known), ('KNOWN_SEEN', self.seen)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def run_step(self, data, code=1, output=''):
        self.report.write_text(data if isinstance(data, str) else json.dumps(data))
        env = dict(os.environ, PATH=f'{self.bin}{os.pathsep}{os.environ["PATH"]}', FAKE_REPORT=str(self.report),
                   FAKE_CODE=str(code), FAKE_OUTPUT=output)
        printed = io.StringIO()
        with open(os.devnull, 'w') as log, patch('sys.stdout', printed):
            passed, failing = customize.run_test_step(['vp', 'test', 'run', FILE], self.source, env, log,
                                                      Path(self.temp.name), self.target)
        return passed, failing, printed.getvalue()

    def test_all_failures_known_pass_and_say_so(self):
        passed, failing, printed = self.run_step(report([(KNOWN, 'failed'), (OTHER, 'passed')]))
        self.assertTrue(passed, failing)
        self.assertIn(f'pass (known upstream failure: {KNOWN})', printed)

    def test_an_unknown_failure_fails_the_step(self):
        passed, failing, _ = self.run_step(report([(KNOWN, 'failed'), (OTHER, 'failed')]))
        self.assertFalse(passed)
        self.assertEqual(failing, [FILE])

    def test_a_file_load_error_is_never_tolerated(self):
        passed, _, _ = self.run_step(report([(KNOWN, 'failed')], message='Failed to load the module'))
        self.assertFalse(passed)

    def test_an_unhandled_error_still_fails(self):
        passed, failing, _ = self.run_step(report([(KNOWN, 'failed')]), output='Unhandled Rejection: boom')
        self.assertFalse(passed)
        self.assertIn('unhandled error', failing[0])

    def test_an_unparsable_report_fails(self):
        passed, failing, _ = self.run_step('{not json')
        self.assertFalse(passed)
        self.assertIn('without a failing file', failing[0])

    def test_a_patched_test_case_is_not_tolerated(self):
        (self.source / FILE).write_text(UPSTREAM.replace('toBeCloseTo(473)', 'toBeCloseTo(470)'))
        passed, failing, _ = self.run_step(report([(KNOWN, 'failed')]))
        self.assertFalse(passed)
        self.assertEqual(failing, [FILE])

    def test_a_patch_elsewhere_in_the_file_keeps_the_entry(self):
        added = '\n  it("patch case", () => {\n    expect(2).toBe(2);\n  });\n});\n'
        (self.source / FILE).write_text(UPSTREAM[:-len('});\n')] + added)
        passed, failing, _ = self.run_step(report([(KNOWN, 'failed'), ('Timeline rows > patch case', 'passed')]))
        self.assertTrue(passed, failing)

    def test_a_test_missing_from_the_nightly_is_not_tolerated(self):
        renamed = 'Timeline rows > keeps the heading put'
        self.known.write_text(json.dumps({'failures': [{'file': FILE, 'test': renamed}]}))
        (self.source / FILE).write_text(UPSTREAM.replace('keeps the heading in place', 'keeps the heading put'))
        passed, _, _ = self.run_step(report([(renamed, 'failed')]))
        self.assertFalse(passed)

    def test_a_passing_entry_is_reported_stale(self):
        passed, _, printed = self.run_step(report([(KNOWN, 'passed'), (OTHER, 'passed')]), code=0)
        self.assertTrue(passed)
        self.assertIn('known upstream failure now passes', printed)
        out = io.StringIO()
        with patch('sys.stdout', out):
            customize.report_known_failures()
        self.assertIn('stale', out.getvalue())
        self.assertIn('remove it', out.getvalue())

    def test_a_failing_entry_is_reported_as_still_failing(self):
        self.run_step(report([(KNOWN, 'failed')]))
        out = io.StringIO()
        with patch('sys.stdout', out):
            customize.report_known_failures()
        self.assertIn('still fails', out.getvalue())

    def test_the_list_is_part_of_the_recipe(self):
        before = customize.recipe_hash()
        self.known.write_text(json.dumps({'failures': []}))
        self.assertNotEqual(before, customize.recipe_hash())


if __name__ == '__main__':
    unittest.main()
