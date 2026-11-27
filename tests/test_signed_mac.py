"""The own signed macOS app (fork): route, identity, Info.plist, entitlements, signing order and install."""
import argparse
import importlib.machinery
import importlib.util
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_prebuild import APP, CURRENT, NEXT, download, make_app

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_signed_mac', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

DEV_ID = 'A' * 40
APPLE_DEV = 'B' * 40
OTHER_DEV_ID = 'C' * 40
LISTING = f'''  1) {APPLE_DEV} "Apple Development: Someone (TEAMID0001)"
  2) {DEV_ID} "Developer ID Application: Example B.V. (TEAMID0001)"
  3) {OTHER_DEV_ID} "Developer ID Application: Other (TEAMID0002)"
     3 valid identities found
'''


class RouteTest(unittest.TestCase):
    def test_a_nightly_without_the_inspector_fuse_takes_the_signed_route(self):
        self.assertEqual(customize.mac_route({'EnableNodeCliInspectArguments': '0'}, False), 'signed')
        self.assertEqual(customize.mac_route({}, False), 'signed')

    def test_a_nightly_with_the_fuse_keeps_the_launcher(self):
        self.assertEqual(customize.mac_route({'EnableNodeCliInspectArguments': '1'}, False), 'launcher')

    def test_a_mac_on_the_signed_copy_stays_on_it(self):
        self.assertEqual(customize.mac_route({'EnableNodeCliInspectArguments': '1'}, True), 'signed')

    def test_never_on_linux(self):
        with patch.object(customize, 'MAC', False), patch.object(customize, 'electron_fuses') as fuses:
            self.assertFalse(customize.signed_route(object()))
            fuses.assert_not_called()


class IdentityTest(unittest.TestCase):
    def test_defaults_to_the_first_developer_id_application_identity(self):
        self.assertEqual(customize.choose_identity(LISTING),
                         (DEV_ID, 'Developer ID Application: Example B.V. (TEAMID0001)'))

    def test_a_configured_identity_by_name_or_hash(self):
        self.assertEqual(customize.choose_identity(LISTING, 'Developer ID Application: Other (TEAMID0002)')[0], OTHER_DEV_ID)
        self.assertEqual(customize.choose_identity(LISTING, APPLE_DEV.lower())[0], APPLE_DEV)

    def test_none_without_a_usable_identity(self):
        self.assertIsNone(customize.choose_identity('     0 valid identities found\n'))
        self.assertIsNone(customize.choose_identity(f'  1) {APPLE_DEV} "Apple Development: X (T)"\n'))
        self.assertIsNone(customize.choose_identity(LISTING, 'Developer ID Application: Missing'))

    def test_a_mac_without_one_stops_with_what_it_needs(self):
        empty = type('Result', (), {'stdout': '     0 valid identities found\n'})()
        with patch.object(customize.subprocess, 'run', return_value=empty), \
                patch.object(customize, 'CONFIG', Path(tempfile.mkdtemp())), \
                patch.dict(customize.os.environ, {}, clear=False):
            customize.os.environ.pop(customize.SIGNING_ENV, None)
            with self.assertRaisesRegex(customize.Stop, 'Developer ID Application.*\n.*stays as it is'):
                customize.signing_identity()


class BundleTest(unittest.TestCase):
    def test_drops_only_the_entitlements_of_t3s_team(self):
        stock = {
            'com.apple.application-identifier': 'TEAM.com.t3tools.t3code',
            'com.apple.developer.associated-domains': ['webcredentials:example.invalid'],
            'com.apple.developer.team-identifier': 'TEAM',
            'keychain-access-groups': ['TEAM.com.t3tools.t3code.webauthn'],
            'com.apple.security.automation.apple-events': True,
            'com.apple.security.cs.allow-jit': True,
            'com.apple.security.cs.allow-unsigned-executable-memory': True,
            'com.apple.security.cs.disable-library-validation': True,
            'com.apple.security.device.audio-input': True,
            'com.apple.security.device.camera': True,
        }
        self.assertEqual(customize.strip_team_entitlements(stock), {
            key: True for key in ('com.apple.security.automation.apple-events', 'com.apple.security.cs.allow-jit',
                                  'com.apple.security.cs.allow-unsigned-executable-memory',
                                  'com.apple.security.cs.disable-library-validation',
                                  'com.apple.security.device.audio-input', 'com.apple.security.device.camera')})

    def test_info_plist_gets_the_new_archive_hash_and_the_marker(self):
        info = {'CFBundleIdentifier': 'com.t3tools.t3code',
                'ElectronAsarIntegrity': {'Resources/app.asar': {'algorithm': 'SHA256', 'hash': 'old'}}}
        marker = {'version': NEXT, 'builtAt': 'now'}
        new = customize.signed_info(info, {'app.asar': 'new'}, marker, validates=False)
        self.assertEqual(new['ElectronAsarIntegrity'], {'Resources/app.asar': {'algorithm': 'SHA256', 'hash': 'new'}})
        self.assertEqual(new['T3CodeCustomize'], marker)
        self.assertEqual(info['ElectronAsarIntegrity']['Resources/app.asar']['hash'], 'old')

    def test_integrity_is_added_only_when_the_app_checks_it(self):
        self.assertNotIn('ElectronAsarIntegrity', customize.signed_info({}, {'app.asar': 'h'}, {}, validates=False))
        self.assertEqual(customize.signed_info({}, {'app.asar': 'h'}, {}, validates=True)['ElectronAsarIntegrity'],
                         {'Resources/app.asar': {'algorithm': 'SHA256', 'hash': 'h'}})

    def test_the_marker_tells_the_copy_from_t3s_app(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        app = make_app(tmp, CURRENT)
        self.assertIsNone(customize.signed_marker(app.path))
        info = plistlib.loads((app.path / 'Contents/Info.plist').read_bytes())
        (app.path / 'Contents/Info.plist').write_bytes(plistlib.dumps(
            customize.signed_info(info, {}, {'version': CURRENT, 'builtAt': 'now'}, False)))
        self.assertEqual(customize.signed_marker(app.path)['version'], CURRENT)

    def test_signs_nested_code_innermost_first_and_skips_symlinks(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        app = tmp / APP
        macho = b'\xcf\xfa\xed\xfe' + b'\0' * 8
        files = {
            'Contents/MacOS/T3 Code (Nightly)': macho,
            'Contents/Frameworks/Electron Framework.framework/Versions/A/Electron Framework': macho,
            'Contents/Frameworks/Electron Framework.framework/Versions/A/Helpers/chrome_crashpad_handler': macho,
            'Contents/Frameworks/Electron Framework.framework/Versions/A/Libraries/libffmpeg.dylib': macho,
            'Contents/Frameworks/T3 Helper.app/Contents/MacOS/T3 Helper': macho,
            'Contents/Resources/app.asar.unpacked/node_modules/pty/pty.node': b'\xca\xfe\xba\xbe\0\0\0\x02',
            'Contents/Resources/app.asar.unpacked/node_modules/pty/linux-x64/pty.node': b'\x7fELF\0\0\0\0',
            'Contents/Resources/Example.class': b'\xca\xfe\xba\xbe\0\0\0\x34',
            'Contents/Resources/app.asar': b'not code',
        }
        for name, data in files.items():
            (app / name).parent.mkdir(parents=True, exist_ok=True)
            (app / name).write_bytes(data)
        framework = app / 'Contents/Frameworks/Electron Framework.framework'
        (framework / 'Versions/Current').symlink_to('A')
        (framework / 'Electron Framework').symlink_to('Versions/Current/Electron Framework')
        order = [p.relative_to(app).as_posix() for p in customize.nested_code(app)]
        self.assertEqual(order, [
            'Contents/Frameworks/Electron Framework.framework/Versions/A/Helpers/chrome_crashpad_handler',
            'Contents/Frameworks/Electron Framework.framework/Versions/A/Libraries/libffmpeg.dylib',
            'Contents/Resources/app.asar.unpacked/node_modules/pty/pty.node',
            'Contents/Frameworks/Electron Framework.framework',
            'Contents/Frameworks/T3 Helper.app',
        ])


class InstallDecisionTest(unittest.TestCase):
    def test_installs_at_once_while_t3_code_is_closed(self):
        self.assertEqual(customize.install_decision(NEXT, CURRENT, running=False, busy=['x']), 'install')

    def test_quits_t3_code_only_when_no_thread_works(self):
        self.assertEqual(customize.install_decision(NEXT, CURRENT, running=True, busy=[]), 'quit')
        self.assertEqual(customize.install_decision(NEXT, CURRENT, running=True, busy=['A thread']), 'wait')

    def test_a_rebuild_of_the_installed_nightly_installs(self):
        self.assertEqual(customize.install_decision(CURRENT, CURRENT, running=False, busy=[]), 'install')

    def test_never_goes_back_to_an_older_nightly(self):
        self.assertEqual(customize.install_decision(CURRENT, NEXT, running=False, busy=[]), 'discard')


class SignedFlowTest(unittest.TestCase):
    """prebuild and install on the signed route, with the build and the Mac tools faked."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.data = self.tmp / 'data'
        self.caches = self.tmp / 'Caches'
        self.installed = make_app(self.tmp / 'Applications', CURRENT)
        patches = [patch.object(customize, 'MAC', True), patch.object(customize, 'SYSTEM', 'darwin'),
                   patch.object(customize, 'DATA', self.data), patch.object(customize, 'CACHE', self.tmp / 'cache'),
                   patch.object(customize, 'STATE', self.data / 'state.json'),
                   patch.object(customize, 'PREBUILT', self.data / 'prebuilt.json'),
                   patch.object(customize, 'SIGNED_PENDING', self.data / 'signed-pending.json'),
                   patch.object(customize, 'STOCK_ARCHIVES', self.data / 'stock'),
                   patch.object(customize, 'ROLLBACK', self.data / 'rollback'),
                   patch.object(customize, 'SHIPIT_STATE', self.caches / 'ShipIt/ShipItState.plist'),
                   patch.object(customize, 'MAC_LAUNCHER', self.tmp / 'Applications/T3 Code (Customized).app'),
                   patch.object(customize, 'MAC_LEGACY_LAUNCHER', self.tmp / 'Applications/T3 Code (Customized).app'),
                   patch.object(customize, 'UPDATER_CACHES', self.caches),
                   patch.object(customize, 'installed_app', side_effect=self.current_app),
                   patch.object(customize, 'signed_route', return_value=True),
                   patch.object(customize, 'verify_signed'),
                   patch.object(customize, 'recipe_hash', return_value='recipe'),
                   patch.object(customize, 'say'), patch.object(customize, 'notify'), patch.object(customize, 'step')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.running, self.busy, self.opened, self.quits = False, [], [], []

    def current_app(self, explicit=None):
        return customize.InstalledApp.inspect(self.installed.path, 'darwin')

    def mac_tools(self, command, **kwargs):
        if command[:3] == ['ditto', '-x', '-k']:
            import zipfile
            zipfile.ZipFile(command[3]).extractall(command[4])
        elif command[:3] == ['ditto', '-c', '-k']:
            Path(command[-1]).write_bytes(b'zip of ' + command[-2].encode())
        elif command[:2] == ['open', str(self.installed.path)]:
            self.opened.append(command[1])

    def built(self, args, stock):
        """cmd_build(stock=...) on the signed route: a signed copy of the downloaded app in builds/."""
        build = self.data / 'builds' / f'{customize.bundle_version(stock.path)}-recipe-job' / APP
        shutil.copytree(stock.path, build)
        info = plistlib.loads((build / 'Contents/Info.plist').read_bytes())
        (build / 'Contents/Info.plist').write_bytes(plistlib.dumps(
            customize.signed_info(info, {}, {'version': customize.bundle_version(stock.path), 'builtAt': 'now'}, False)))
        return {'version': customize.bundle_version(stock.path), 'commit': 'abc', 'recipe': 'recipe',
                'build': str(build), 'connect': True, 'builtAt': 'now'}

    def prebuild(self):
        args = argparse.Namespace(app=None, fix=None, background=True)
        with patch.object(customize, 'cmd_build', side_effect=self.built) as cmd_build, \
                patch.object(customize, 'run', side_effect=self.mac_tools), \
                patch.object(customize.subprocess, 'run', side_effect=self.mac_tools), \
                patch.object(customize, 'main_app_pids', side_effect=lambda app: [42] if self.running else []), \
                patch.object(customize, 'quit_app', side_effect=self.quit), \
                patch.object(customize, 'busy_threads', side_effect=lambda: self.busy):
            # install_signed_pending binds busy_threads as its default; call through the module.
            with patch.object(customize, 'install_signed_pending',
                              side_effect=lambda background=False: self.install(background)):
                result = customize.prebuild_quietly(args)
        return result, cmd_build

    def install(self, background):
        return self.real_install(background=background, busy=lambda: self.busy)

    real_install = staticmethod(customize.install_signed_pending)

    def quit(self, app_path):
        self.quits.append(app_path)
        self.running = False

    def release(self):
        return make_app(self.tmp / 'release', NEXT, contents=b'{"v":2}', executable=b'exe2')

    def test_builds_the_download_and_installs_it_over_t3s_app_while_closed(self):
        archive = download(self.caches, self.release())
        self.data.mkdir(parents=True)
        customize.save(customize.PREBUILT, {'version': CURRENT})
        launcher = self.tmp / 'Applications/T3 Code (Customized).app'
        launcher.mkdir()
        result, cmd_build = self.prebuild()
        self.assertTrue(result)
        cmd_build.assert_called_once()
        # Never a prebuilt.json: T3's updater would hand the download to Squirrel.
        self.assertFalse(customize.PREBUILT.exists())
        self.assertFalse(customize.SIGNED_PENDING.exists())
        self.assertEqual(customize.bundle_version(self.installed.path), NEXT)
        self.assertEqual(customize.signed_marker(self.installed.path)['version'], NEXT)
        state = customize.load(customize.STATE)
        self.assertEqual((state['route'], state['version'], state['build']), ('signed', NEXT, str(self.installed.path)))
        # T3's own app of the download stays as the source of a rebuild; the launcher is gone.
        self.assertEqual(Path(state['stockArchive']).read_bytes(), archive.read_bytes())
        self.assertFalse(launcher.exists())
        self.assertEqual((self.quits, self.opened), ([], []))
        # T3's own app it replaced is kept once, zipped, as the way back.
        self.assertEqual([p.name for p in (self.data / 'rollback').iterdir()], [CURRENT + '.zip'])
        self.assertFalse((self.data / 'builds').exists() and any((self.data / 'builds').iterdir()))

    def test_waits_while_a_thread_works_then_quits_installs_and_reopens(self):
        download(self.caches, self.release())
        self.running, self.busy = True, ['A busy thread']
        result, _ = self.prebuild()
        self.assertTrue(result)
        pending = customize.load(customize.SIGNED_PENDING)
        self.assertEqual(pending['version'], NEXT)
        self.assertEqual(customize.bundle_version(self.installed.path), CURRENT)
        self.assertEqual(self.quits, [])
        # The next run finds it built and only installs, once idle.
        self.busy = []
        self.caches.joinpath('ShipIt').mkdir(parents=True)
        customize.SHIPIT_STATE.write_text('{}')
        result, cmd_build = self.prebuild()
        self.assertFalse(result)
        cmd_build.assert_not_called()
        self.assertEqual(customize.bundle_version(self.installed.path), NEXT)
        self.assertEqual(self.quits, [self.installed.path])
        self.assertEqual(self.opened, [str(self.installed.path)])
        self.assertFalse(customize.SHIPIT_STATE.exists())


if __name__ == '__main__':
    unittest.main()
