import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_skip', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

STATS = 'Stats for Nerds: response throughput and the composer stats line'


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


class SkipSharedTest(unittest.TestCase):
    """A fork-owned skip-shared.json leaves shared patches and their checks.json entries out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.recipe = self.root / 'recipe'
        self.source = self.root / 'source'
        self.source.mkdir()
        git(self.source, 'init', '-q')
        (self.source / 'app.ts').write_text('base\n')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'base')
        self.base = git(self.source, 'rev-parse', 'HEAD').strip()
        # Three shared patches; the middle one has a long subject that format-patch folds.
        for name, subject in (('a.ts', 'Usage limits: polling'),
                              ('stats.ts', STATS + ' that format-patch folds onto a second header line'),
                              ('c.ts', 'fix(tests): honor Windows filesystem modes')):
            (self.source / name).write_text(name + '\n')
            git(self.source, 'add', name)
            git(self.source, 'commit', '-qm', subject)
        for folder in ('patches', 'patches-port'):
            git(self.source, 'format-patch', '--quiet', '--no-signature', '--zero-commit', '-o',
                str(self.recipe / folder), self.base + '..HEAD')
            (self.recipe / folder / 'base.txt').write_text(self.base + '\n')
        git(self.source, 'checkout', '-q', '--detach', self.base)
        (self.recipe / 'patches-tt').mkdir()
        (self.recipe / 'checks.json').write_text(json.dumps({
            'tests': ['a.test.ts', 'stats.test.ts'], 'typecheck': ['apps/web']}))
        (self.recipe / 'checks-tt.json').write_text(json.dumps({'tests': ['stats.test.ts', 'own.test.ts']}))
        for name, value in (('SOURCE', self.source), ('RECIPE', self.recipe), ('SHARED', self.recipe / 'patches'),
                            ('PORT', self.recipe / 'patches-port'), ('OWN_PATCHES', self.recipe / 'patches-tt'),
                            ('OWN_CHECKS', self.recipe / 'checks-tt.json'), ('WITH_IOS', False)):
            patcher = patch.object(customize, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def skip(self, subjects, checks=()):
        (self.recipe / customize.SKIP_SHARED).write_text(json.dumps({
            'patches': [{'subject': s, 'reason': 'test'} for s in subjects], 'checks': list(checks)}))

    def subjects(self):
        return [customize.patch_subject(p) for p in customize.patches()]

    def test_the_subject_is_unfolded_without_its_patch_prefix(self):
        stats = sorted((self.recipe / 'patches').glob('0002-*.patch'))[0]
        self.assertIn('\n ', stats.read_text().split('\n\n', 1)[0], 'format-patch should fold this subject')
        self.assertEqual(customize.patch_subject(stats),
                         STATS + ' that format-patch folds onto a second header line')

    def test_a_non_ascii_subject_is_decoded(self):
        (self.source / 'd.ts').write_text('d\n')
        git(self.source, 'add', 'd.ts')
        git(self.source, 'commit', '-qm', 'feat: café')
        out = self.root / 'encoded'
        git(self.source, 'format-patch', '--quiet', '--zero-commit', '-o', str(out), 'HEAD~1..HEAD')
        patch_file = sorted(out.glob('*.patch'))[0]
        self.assertIn('=?UTF-8?', patch_file.read_text())
        self.assertEqual(customize.patch_subject(patch_file), 'feat: café')

    def test_without_a_skip_file_every_shared_patch_applies(self):
        self.assertEqual(len(customize.patches()), 3)
        customize.check_skips()

    def test_a_skipped_subject_is_left_out_of_patches_and_patches_port(self):
        self.skip([STATS + ' that format-patch folds onto a second header line'])
        self.assertEqual(self.subjects(), ['Usage limits: polling', 'fix(tests): honor Windows filesystem modes'])
        with patch.object(customize, 'SHARED', self.recipe / 'patches-port'):
            self.assertEqual(len(customize.patches()), 2)

    def test_a_renumbered_patch_stays_out(self):
        self.skip([STATS + ' that format-patch folds onto a second header line'])
        stats = sorted((self.recipe / 'patches').glob('0002-*.patch'))[0]
        stats.rename(stats.with_name('0009-renumbered.patch'))
        self.assertNotIn('0009-renumbered.patch', [p.name for p in customize.patches()])
        customize.check_skips()

    def test_a_subject_upstream_no_longer_has_stops_the_run(self):
        # Upstream renamed the patch: without the stop it would come back under its new subject.
        self.skip(['Stats for Nerds (old name)'])
        with self.assertRaises(customize.Stop) as raised:
            customize.check_skips()
        self.assertIn('Stats for Nerds (old name)', str(raised.exception))
        self.assertEqual(customize.unmatched_skips(), ['Stats for Nerds (old name)'])
        with self.assertRaises(customize.Stop):
            customize.choose_shared(io.StringIO())

    def test_skips_match_against_upstream_patches_even_when_the_port_left_them_out(self):
        # A port export writes patches-port/ without the skipped patch; upstream's patches/ still has it.
        subject = STATS + ' that format-patch folds onto a second header line'
        self.skip([subject])
        for path in (self.recipe / 'patches-port').glob('0002-*.patch'):
            path.unlink()
        customize.check_skips()
        with patch.object(customize, 'SHARED', self.recipe / 'patches-port'):
            self.assertEqual(len(customize.patches()), 2)

    def test_skipped_checks_leave_checks_json_but_not_own_lists(self):
        self.skip([], checks=['stats.test.ts', 'apps/web'])
        spec = customize.check_spec()
        self.assertEqual(spec['tests'], ['a.test.ts', 'stats.test.ts', 'own.test.ts'])
        self.assertEqual(spec['typecheck'], [])
        self.skip([], checks=['stats.test.ts'])
        (self.recipe / 'checks-tt.json').write_text(json.dumps({'tests': ['own.test.ts']}))
        self.assertEqual(customize.check_spec()['tests'], ['a.test.ts', 'own.test.ts'])

    def test_the_skip_file_is_part_of_the_check_lists_and_the_recipe(self):
        self.assertIn(customize.SKIP_SHARED, customize.RECIPE_FILES)
        before = customize.check_lists_hash()
        self.skip([], checks=['stats.test.ts'])
        self.assertNotEqual(customize.check_lists_hash(), before)
        with patch.object(customize, 'REPO', self.recipe):
            (self.recipe / 'macos').mkdir()
            (self.recipe / customize.NAME).write_text('# script\n')
            (self.recipe / 'platform_support.py').write_text('# support\n')
            hashed = customize.recipe_hash()
            self.skip([], checks=['other.test.ts'])
            self.assertNotEqual(customize.recipe_hash(), hashed)

    def test_prepare_applies_only_the_kept_shared_patches(self):
        self.skip([STATS + ' that format-patch folds onto a second header line'])
        with open(self.root / 'log', 'w') as log, patch.object(customize, 'say', lambda *a, **k: None):
            customize.prepare(self.base, log)
        files = git(self.source, 'ls-files').split()
        self.assertEqual(sorted(files), ['a.ts', 'app.ts', 'c.ts'])
        self.assertEqual(git(self.source, 'rev-list', '--count', self.base + '..HEAD').strip(), '2')

    def test_the_fork_skip_file_matches_upstream_patches(self):
        # The repo's own skip-shared.json: every subject names a patch in upstream's patches/, and every
        # check it leaves out is in checks.json.
        with patch.object(customize, 'RECIPE', ROOT):
            self.assertEqual(customize.unmatched_skips(), [])
            listed = json.loads((ROOT / 'checks.json').read_text())
            for check in customize.shared_skips().get('checks', []):
                self.assertIn(check, listed['tests'] + listed['typecheck'])


if __name__ == '__main__':
    unittest.main()


class BundleMarkersTest(unittest.TestCase):
    """The bundle check looks for skip-shared.json's markers, since the default ones come from a shared patch."""

    def test_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Path(tmp)
            with patch.object(customize, 'RECIPE', recipe):
                self.assertEqual(customize.bundle_markers(),
                                 tuple((prefix, (marker,)) for prefix, marker in customize.MARKERS))
                (recipe / customize.SKIP_SHARED).write_text(json.dumps({'patches': [], 'markers': [
                    ['apps/server/dist/client/', 'openedByThreadId']]}))
                self.assertIn(('apps/server/dist/client/', (b'statsForNerds', b'openedByThreadId')),
                              customize.bundle_markers())

    def test_server_build_markers(self):
        """The server build checks the web client and the executable with the same markers as the bundles."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Path(tmp)
            with patch.object(customize, 'RECIPE', recipe):
                (recipe / customize.SKIP_SHARED).write_text(json.dumps({'patches': [], 'markers': [
                    ['apps/server/dist/client/', 'openedByThreadId'], ['apps/server/dist/', 'direct-push-apns']]}))
                self.assertEqual(customize.server_build_markers(), (
                    ('apps/server/dist/client', (b'statsForNerds', b'openedByThreadId'), True),
                    ('apps/server/dist-exe', (b'claude_observed', b'direct-push-apns'), False)))

    def test_repo_markers_come_from_kept_patches(self):
        """Every marker in this repo's skip-shared.json appears in a patch the fork still applies."""
        skips = json.loads((ROOT / customize.SKIP_SHARED).read_text())
        skipped = {entry['subject'] for entry in skips['patches']}
        kept = [p for folder in ('patches-port', 'patches-tt') for p in sorted((ROOT / folder).glob('*.patch'))
                if customize.patch_subject(p) not in skipped]
        self.assertEqual({prefix for prefix, _ in skips['markers']}, {prefix for prefix, _ in customize.MARKERS})
        for _, marker in skips['markers']:
            self.assertTrue(any(marker in p.read_text(encoding='utf-8', errors='replace') for p in kept), marker)
