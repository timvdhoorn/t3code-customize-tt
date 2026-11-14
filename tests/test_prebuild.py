import argparse
import base64
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize_prebuild', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)

APP = 'T3 Code (Nightly).app'
CURRENT = '0.1.10-nightly.20261112.4564'
NEXT = '0.1.10-nightly.20261114.4682'


def asar(contents):
    """A minimal asar archive: a JSON header and the file data."""
    header = json.dumps({'files': {'package.json': {'size': len(contents), 'offset': '0'}}}).encode()
    padded = header + b'\0' * ((-len(header)) % 4)
    return struct.pack('<4I', 4, len(padded) + 8, len(padded) + 4, len(header)) + padded + contents


def make_app(folder, version, contents=b'{}', executable=b'exe'):
    app = folder / APP
    (app / 'Contents/MacOS').mkdir(parents=True)
    (app / 'Contents/Resources').mkdir(parents=True)
    (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString': version}))
    (app / 'Contents/MacOS/T3 Code (Nightly)').write_bytes(executable)
    (app / 'Contents/Resources/app.asar').write_bytes(asar(contents))
    (app / 'Contents/Resources/app-update.yml').write_text('provider: github\nupdaterCacheDirName: t3code-updater\n')
    return customize.InstalledApp.inspect(app, 'darwin')


def download(caches, source_app, digest=None):
    """What electron-updater leaves in its pending folder after a finished download."""
    pending = caches / 't3code-updater/pending'
    pending.mkdir(parents=True)
    name = 'T3-Code-update-arm64.zip'
    with zipfile.ZipFile(pending / name, 'w') as archive:
        for path in sorted(source_app.path.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(source_app.path.parent).as_posix())
    sha = base64.b64encode(hashlib.sha512((pending / name).read_bytes()).digest()).decode()
    (pending / 'update-info.json').write_text(json.dumps({'fileName': name, 'sha512': digest or sha}))
    return pending / name


class PrebuildTest(unittest.TestCase):
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
                   patch.object(customize, 'UPDATER_CACHES', self.caches),
                   patch.object(customize, 'say'), patch.object(customize, 'notify')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def new_release(self, **kwargs):
        return make_app(self.tmp / 'release', NEXT, contents=b'{"v":2}', executable=b'exe2')

    # --- Finding the download -------------------------------------------------------------

    def test_finds_a_complete_download_newer_than_the_installed_app(self):
        archive = download(self.caches, self.new_release())
        self.assertEqual(customize.downloaded_update(self.installed), (archive, NEXT))

    def test_ignores_a_download_that_is_incomplete_or_not_newer(self):
        download(self.caches, self.new_release(), digest='bm90IHRoaXMgZmlsZQ==')
        self.assertIsNone(customize.downloaded_update(self.installed))
        shutil.rmtree(self.caches)
        download(self.caches, make_app(self.tmp / 'same', CURRENT))
        self.assertIsNone(customize.downloaded_update(self.installed))
        shutil.rmtree(self.caches)
        self.assertIsNone(customize.downloaded_update(self.installed))

    # --- Identity across the install ------------------------------------------------------

    def test_the_identity_of_a_copy_ignores_where_and_when_it_was_written(self):
        release = self.new_release()
        installed = self.tmp / 'Applications2'
        shutil.copytree(release.path.parent, installed)
        copy = customize.InstalledApp.inspect(installed / APP, 'darwin')
        os.utime(copy.resources / 'app.asar', (1, 1))
        self.assertNotEqual(release.fingerprint(), copy.fingerprint())
        self.assertEqual(customize.stock_identity(release), customize.stock_identity(copy))
        self.assertNotEqual(customize.stock_identity(release), customize.stock_identity(self.installed))

    # --- Prebuilding ----------------------------------------------------------------------

    def run_prebuild(self, build):
        args = argparse.Namespace(app=None, fix=None, background=True)
        with patch.object(customize, 'installed_app', return_value=self.installed), \
                patch.object(customize, 'cmd_build', side_effect=build) as cmd_build, \
                patch.object(customize, 'recipe_hash', return_value='recipe'), \
                patch.object(customize, 'run', side_effect=self.unzip):
            result = customize.prebuild_quietly(args)
        return result, cmd_build

    @staticmethod
    def unzip(command, **kwargs):
        # ditto -x -k <zip> <folder> on macOS.
        zipfile.ZipFile(command[3]).extractall(command[4])

    def built(self, args, stock):
        build = self.data / 'builds/next/build'
        build.mkdir(parents=True)
        self.seen = (stock.path.name, customize.bundle_version(stock.path), args.no_pull)
        return {'version': NEXT, 'commit': 'abc', 'recipe': 'recipe', 'build': str(build),
                'connect': True, 'builtAt': 'now'}

    def test_builds_the_downloaded_nightly_before_it_is_installed_and_names_it(self):
        release = self.new_release()
        download(self.caches, release)
        customize.save(customize.STATE, {'version': CURRENT, 'build': 'current-build'})
        result, cmd_build = self.run_prebuild(self.built)
        self.assertTrue(result)
        # Built from the downloaded app, not the installed one; the current build stays.
        self.assertEqual(self.seen, (APP, NEXT, True))
        self.assertEqual(customize.load(customize.STATE)['build'], 'current-build')
        prebuilt = customize.load(customize.PREBUILT)
        self.assertEqual(prebuilt['version'], NEXT)
        self.assertEqual(prebuilt['identity'], customize.stock_identity(release))
        customize.notify.assert_called_once()
        self.assertFalse((self.tmp / 'cache/prebuild').exists() and any((self.tmp / 'cache/prebuild').iterdir()))
        # The next run finds it done.
        result, cmd_build = self.run_prebuild(self.built)
        self.assertFalse(result)
        cmd_build.assert_not_called()

    def test_a_failed_prebuild_names_nothing_and_keeps_the_current_build(self):
        download(self.caches, self.new_release())
        customize.save(customize.STATE, {'version': CURRENT, 'build': 'current-build'})
        for failure in (customize.NeedsFix('conflict'), customize.Stop('checks failed'),
                        customize.PortHandedOff('handed off')):
            result, _ = self.run_prebuild(failure)
            self.assertFalse(result)
            self.assertFalse(customize.PREBUILT.exists())
            self.assertEqual(customize.load(customize.STATE)['build'], 'current-build')

    def test_nothing_to_prebuild_without_a_download(self):
        result, cmd_build = self.run_prebuild(self.built)
        self.assertFalse(result)
        cmd_build.assert_not_called()

    # --- After the install ----------------------------------------------------------------

    def test_the_launcher_opens_the_prebuilt_build_once_its_nightly_is_installed(self):
        release = self.new_release()
        build = self.data / 'builds/next/build'
        (build).mkdir(parents=True)
        (build / 'inject.cjs').write_text('')
        customize.save(customize.STATE, {'stock': self.installed.fingerprint(), 'version': CURRENT,
                                         'build': str(self.tmp / 'old/build/inject.cjs')})
        customize.save(customize.PREBUILT, {'version': NEXT, 'commit': 'abc', 'recipe': 'recipe',
                                            'build': str(build), 'connect': True, 'builtAt': 'now',
                                            'identity': customize.stock_identity(release)})
        with patch.object(customize, 'DISABLED', self.tmp / 'disabled'):
            # Before the install: the prebuilt build is not used.
            with patch.object(customize, 'installed_app', return_value=self.installed):
                self.assertFalse(customize.promote_prebuilt(self.installed))
            # Squirrel moved the downloaded app into place.
            shutil.rmtree(self.installed.path)
            shutil.copytree(release.path, self.installed.path)
            with patch.object(customize, 'installed_app', return_value=self.installed):
                target, notice = customize.launch_target()
        self.assertEqual(target, build.resolve())
        self.assertIsNone(notice)
        state = customize.load(customize.STATE)
        self.assertEqual((state['version'], state['build'], state['stock']),
                         (NEXT, str(build), self.installed.fingerprint()))

    def test_a_prebuilt_build_for_another_release_is_not_used(self):
        other = make_app(self.tmp / 'other', NEXT, contents=b'{"v":3}')
        build = self.data / 'builds/next/build'
        build.mkdir(parents=True)
        customize.save(customize.PREBUILT, {'version': NEXT, 'build': str(build),
                                            'identity': customize.stock_identity(other)})
        self.assertFalse(customize.promote_prebuilt(self.installed))
        self.assertFalse(customize.STATE.exists())

    def test_prune_keeps_the_prebuilt_build(self):
        builds = self.data / 'builds'
        for index, name in enumerate(('prebuilt', 'a', 'b', 'c', 'current')):
            (builds / name / 'build').mkdir(parents=True)
            os.utime(builds / name, (index, index))
        customize.save(customize.STATE, {'build': str(builds / 'current/build')})
        customize.save(customize.PREBUILT, {'build': str(builds / 'prebuilt/build')})
        customize.prune(keep=2)
        self.assertEqual(sorted(p.name for p in builds.iterdir()), ['c', 'current', 'prebuilt'])

    def test_the_launch_agent_watches_the_updater_download(self):
        plist = self.tmp / 'LaunchAgents/agent.plist'
        args = argparse.Namespace(state='on', fix=None, ios=False, every=60)
        with patch.object(customize, 'AUTOUPDATE_PLIST', plist), \
                patch.object(customize, 'installed_app', return_value=self.installed), \
                patch.object(customize.subprocess, 'run',
                             side_effect=lambda command, **kwargs: customize.subprocess.CompletedProcess(command, 0)), \
                patch.object(customize, 'run'), patch.object(customize.time, 'sleep'):
            customize.cmd_autoupdate(args)
        watched = plistlib.loads(plist.read_bytes())['WatchPaths']
        self.assertIn(str(self.caches / 't3code-updater/pending'), watched)


if __name__ == '__main__':
    unittest.main()
