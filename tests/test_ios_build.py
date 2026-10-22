import importlib.machinery
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_ios', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def write_app(path, version, bundle_id='com.t3tools.t3code'):
    (path / 'Contents').mkdir(parents=True, exist_ok=True)
    (path / 'Contents/Info.plist').write_bytes(plistlib.dumps(
        {'CFBundleShortVersionString': version, 'CFBundleIdentifier': bundle_id}))


class InstallScriptsTest(unittest.TestCase):
    def setUp(self):
        self.source = Path(tempfile.mkdtemp())
        mobile = self.source / 'apps/mobile'
        write_json(mobile / 'package.json', {'dependencies': {'react-native-enriched-markdown': '*', 'plain': '*',
                                                              'brand-new': '*', 'gone': '*'},
                                             'devDependencies': {'typescript': '*'}})
        write_json(mobile / 'node_modules/react-native-enriched-markdown/package.json',
                   {'scripts': {'postinstall': 'node postinstall.mjs', 'test': 'jest'}})
        write_json(mobile / 'node_modules/plain/package.json', {'scripts': {'test': 'jest'}})
        write_json(mobile / 'node_modules/brand-new/package.json', {'scripts': {'install': 'node-gyp rebuild'}})
        write_json(mobile / 'node_modules/typescript/package.json', {'scripts': {'postinstall': 'node lib/install.js'}})
        patch.object(customize, 'SOURCE', self.source).start()
        self.addCleanup(patch.stopall)

    def test_lists_direct_dependencies_with_an_install_script(self):
        self.assertEqual(customize.mobile_install_scripts(),
                         ['brand-new', 'react-native-enriched-markdown', 'typescript'])

    def test_checks_with_the_ios_layer_name_an_unsorted_one(self):
        patch.object(customize, 'WITH_IOS', True).start()
        patch.object(customize, 'checks_stamped', lambda target: False).start()
        patch.object(customize, 'check_spec', lambda: {'tests': [], 'typecheck': []}).start()
        with self.assertRaises(customize.NeedsFix) as stop:
            customize.checks({}, None, 'base')
        self.assertIn('  brand-new\n', str(stop.exception))
        self.assertNotIn('typescript', str(stop.exception))
        self.assertNotIn('  react-native-enriched-markdown', str(stop.exception))

    def test_checks_without_the_ios_layer_skip_it(self):
        patch.object(customize, 'WITH_IOS', False).start()
        patch.object(customize, 'checks_stamped', lambda target: False).start()
        patch.object(customize, 'check_spec', lambda: {'tests': [], 'typecheck': []}).start()
        patch.object(customize, 'step', side_effect=StopIteration).start()
        with self.assertRaises(StopIteration):  # got past the install-script check
            customize.checks({}, None, 'base')


class PodInstallErrorTest(unittest.TestCase):
    def test_names_the_first_pod_error_of_this_prebuild(self):
        log = Path(tempfile.mkdtemp()) / 'ios.log'
        log.write_text('> pod install\n[!] Old error\n✔ Finished prebuild\n'
                       '- Installing CocoaPods...\n> pod install\n'
                       '\x1b[31m\n[!] Invalid `Podfile` file: \x1b[31m\n'
                       '[!] Invalid `X.podspec` file: assets are missing.\n\x1b[0m\n')
        self.assertEqual(customize.pod_install_error(log), '\npod install failed: [!] Invalid `X.podspec` file: assets are missing.')

    def test_says_nothing_without_one(self):
        log = Path(tempfile.mkdtemp()) / 'ios.log'
        log.write_text('> pod install\nall fine\n')
        self.assertEqual(customize.pod_install_error(log), '')
        self.assertEqual(customize.pod_install_error(log.with_name('missing.log')), '')


class StagedAppUpdateTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        patch.object(customize.Path, 'home', lambda: self.home).start()
        self.addCleanup(patch.stopall)
        self.app = self.home / 'Applications/T3 Code (Nightly).app'
        write_app(self.app, '0.1.1-nightly.3302')
        self.shipit = self.home / 'Library/Caches/com.t3tools.t3code.ShipIt'

    def stage(self, version):
        bundle = self.shipit / 'update.abc/T3 Code (Nightly).app'
        write_app(bundle, version)
        write_json(self.shipit / 'ShipItState.plist', {'updateBundleURL': bundle.as_uri() + '/'})

    def test_reports_a_staged_newer_version(self):
        self.stage('0.1.2-nightly.3541')
        self.assertEqual(customize.staged_app_update(self.app), '0.1.2-nightly.3541')

    def test_nothing_once_installed_or_without_state(self):
        self.assertIsNone(customize.staged_app_update(self.app))
        self.stage('0.1.1-nightly.3302')
        self.assertIsNone(customize.staged_app_update(self.app))

    def test_nothing_when_the_staged_bundle_is_gone(self):
        write_json(self.shipit / 'ShipItState.plist', {'updateBundleURL': (self.shipit / 'update.gone/T3.app').as_uri()})
        self.assertIsNone(customize.staged_app_update(self.app))

    def test_nothing_for_a_state_file_that_is_not_json(self):
        self.shipit.mkdir(parents=True)
        (self.shipit / 'ShipItState.plist').write_bytes(plistlib.dumps({'a': 1}, fmt=plistlib.FMT_BINARY))
        self.assertIsNone(customize.staged_app_update(self.app))


if __name__ == '__main__':
    unittest.main()
