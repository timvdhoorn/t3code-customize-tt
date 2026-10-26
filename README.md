# t3code-customize-tt

Tim's build of T3 Code Nightly: the stats bar under the composer, plus his own fixes and
features, on his Macs, his Linux server and his iPhone. One command rebuilds it after every
T3 Code update.

Unofficial. Not affiliated with T3 Tools. Built on
[btsouth/t3code-customize](https://github.com/btsouth/t3code-customize) (see [Credits](#credits)).
For T3 Code Nightly on macOS, a headless Linux T3 server, a Linux AppImage, Windows (untested here) and iOS (TestFlight).

## What you get

**Stats for nerds** under the composer (the shared patches in `patches/`, from upstream):

- **Usage meters** for your 5 hour and weekly limits, from the limits T3 already gets from your providers.
- **Context** used in the thread. Hover it for the window size, the auto-compaction threshold and a Compact now button.
- **Tokens per second** for the last response, with turn time and token details on hover. Claude rates are measured from the stream; Codex rates are labeled approximate.
- **Cache rate** for the last turn.
- **Subscription switch** when you have more than one signed-in subscription that offers your model. If the current one is on pace to run out before its 5 hour or weekly window resets, a chip like **Opus 5.5 on Personal →** switches the thread to the same model on the one with the most room. It also points out a subscription whose weekly allowance resets within a day mostly unused. Hover it for the reasoning.

**Own changes** (`patches-tt/`, on top of the shared patches):

- **Claude context window** measured against the smaller of the model window and Claude's `autoCompactWindow` setting.
- **Worktree handoff** continues in the new worktree instead of failing with "Provider event stream closed unexpectedly" (a port of upstream PR #15203).
- **Child threads** nest under the thread that opened them in the sidebar, with their status, as in Claude.app.
- **Direct push**: your own servers send notifications and Live Activity updates to your iPhone over APNs.

**iOS app** (`patches-ios/`, TestFlight under your own Apple team): the same stats line, nested
child threads and direct push, JetBrains Sans and JetBrains Mono as the fonts, and the desktop's Claude theme.

Everything else is stock T3 Code, including T3 Connect.

## Install

Install T3 Code **Nightly** first. You need Git, Python **3.9+**, an internet
connection and at least approximately **6 GB** of free space. If Node is older
than 24, the tool downloads a private, checksum-verified Node 24 for the host.
The first build takes approximately 5 to 15 minutes, depending on the machine.

### Windows (PowerShell)

Install Git for Windows and Python, with `git` and `python.exe` on PATH. Clone
this repository, then run Python directly; Git Bash and administrator access are not
required:

```powershell
git clone https://github.com/timvdhoorn/t3code-customize-tt.git
cd t3code-customize-tt
python .\t3code-customize build
```

For a nonstandard installation location, pass the **installed executable**,
not the NSIS installer:

```powershell
python .\t3code-customize build --app 'C:\Apps\T3 Code\T3 Code (Nightly).exe'
```

Alternatively, run the checked-out `install.ps1`; it clones this repository into the
tool's private data directory and builds it. Use `-App` for an explicit executable
and `-Branch` when testing a feature branch. It does not change execution policy.

### Linux and macOS

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/timvdhoorn/t3code-customize-tt/main/install.sh)"
```

Or clone this repository and run `python3 ./t3code-customize build`. AppImages in
`~/Applications`, `~/Downloads` and the other standard tool search directories
are discovered automatically. For other paths, pass
`--app /path/to/T3-Code.AppImage`. The old `--appimage` option still works.

### Enable the stats

After the build succeeds, **quit T3 Code fully**. Open **T3 Code (Customized)**
from the Windows Start menu, the Linux app launcher or Spotlight on macOS.
Enable **Settings > General > Stats for nerds**.

The customized app opens the normal T3 Code main screen; it does not show a
separate setup wizard. Open Settings manually and search for **Stats for nerds**
if you cannot find the switch. It is off by default. Once enabled, the stats
appear below the chat composer; which values are available depends on the
provider and the conversation.

The command wrapper lives in `~/.local/bin` on Linux, or
`%LOCALAPPDATA%\t3code-customize\bin` on Windows. If it is not on PATH, add that
directory or use `python t3code-customize <command>` from the checkout
(`python3` on Linux).

On macOS, open **T3 Code (Customized)** from Spotlight, Launchpad or `/Applications`. See the [macOS guide](docs/macos.md) for setup, day-to-day use and why it loads the patches into your app instead of rebuilding it. It looks for `T3 Code (Nightly).app` in `/Applications` and `~/Applications`; point it elsewhere once with `--app "/path/to/T3 Code (Nightly).app"`.

## After every T3 Code update

```sh
t3code-customize
```

Update the **official app** first, then run the tool. It pulls the latest patches,
rebuilds for your installed version and tells you when to reopen. Until you run
it, the launcher falls back to stock T3 Code. Windows customized copies
have automatic updates disabled; update stock from its original launcher.

## When a nightly breaks the patches

Upstream moves fast, and sometimes a nightly changes the code the patches touch. When that happens:

- If you have Claude Code or Codex installed, it offers to port the patches for you right there.
- Or point any coding agent at this repo and ask it to follow [AGENTS.md](AGENTS.md); the port itself is in [docs/porting.md](docs/porting.md).
- The shared patches may also catch up in [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize); each run merges that in when it merges cleanly. The own patches in `patches-tt/` and `patches-ios/` are only ported here.

Your current T3 Code keeps working the whole time.

## macOS

Your `T3 Code (Nightly).app` stays exactly as T3 ships it, so it keeps its signature, passkeys,
keychain access and T3's own updater. Open **T3 Code (Customized)** from Spotlight, Launchpad or
`/Applications`: it starts your app and loads the rebuilt bundles into it. Started any other way
(Dock, Finder, a `t3code://` link) T3 Code runs stock. See the [macOS guide](docs/macos.md).

```sh
t3code-customize                 rebuild for the T3 Code installed now
t3code-customize autoupdate on   rebuild by itself whenever T3 Code updates (LaunchAgent)
t3code-customize status          versions, what the launcher opens, background updates
```

T3 Code updates itself as usual. With `autoupdate on`, the rebuild starts as soon as T3 has
installed the update, and a notification tells you when to quit T3 Code and reopen the
launcher. Until then T3 Code runs stock; a launcher opened in between starts the rebuild itself.
The label next to the T3 logo shows which customized build you run (the first characters of the recipe in `status`; hover it for the build time). Settings > General > About and the macOS About panel show it too.

When a nightly changes code the patches touch, you get a notification and T3 Code stays stock.
With a porter in `machines.json` (the machine with `"fix"`, here devbox1) the Mac hands the port to
it and notifies "port running on devbox1"; the porter runs `t3code-customize port`, one agent session
for every stage and the checks, opens a PR and, under the standing grant in
[docs/machines.md](docs/machines.md#unattended-ports), merges it and runs `t3code-customize fleet`.
Without a porter, ask a coding agent in this repo to port the patches ([docs/porting.md](docs/porting.md)),
or turn on `autoupdate on --fix claude` so Claude Code ports them on this machine.

## iOS app (TestFlight)

`t3code-customize ios` builds upstream's Expo app (`apps/mobile`) with the patches, signed with
your own Apple team and bundle identifier, and uploads it to TestFlight. It uses the nightly
commit of the T3 Code installed on the Mac, so the app matches your servers. Run it on a Mac
with Xcode, CocoaPods and [asc-cli](https://github.com/tddworks/asc-cli) (`brew install asccli`).

```sh
t3code-customize ios             build and upload when the nightly or the patches changed
t3code-customize ios --force     build and upload anyway
```

`ios.json` holds the identity (bundle identifier, team, app name), the App Store Connect API key
ID and issuer ID, and the internal TestFlight group with its testers. The `.p8` key lives in
`~/.asc/keys/AuthKey_<key id>.p8` (mode 600) and in 1Password ("App Store Connect API key
t3code-customize"). The first run creates the App Store Connect app through asc-cli's private
API, which reads your App Store Connect session from the browser, so sign in there first. Xcode
registers the extension identifiers, app group and profiles itself with the API key.

Internal testers must be members of the App Store Connect team; accept the invitation before
the tool can add you to the group. Install the build from the TestFlight app.

Patches only the iOS app needs live in `patches-ios/` (checks in `checks-ios.json`); only this
command applies them. The build takes T3 Connect's public config from the installed Mac app, as the
official build has it. Differences from the official app: no passkeys, Sign in with Apple or
Google sign-in, and no over-the-air updates (all are bound to T3's team or bundle identifier). Pair
the app with your servers directly, over Tailscale, or sign in to T3 Connect.

Push notifications and Live Activity updates come from your own servers instead of T3's relay
(`patches-tt/0004`, `patches-ios/0005`). Each server needs your team's APNs key as
`~/.t3/userdata/secrets/direct-push-apns.bin` (JSON with `teamId`, `keyId`, `privateKey`, `bundleId` and `environment`, mode 600; the 1Password item "T3 Code TT APNs key", field `serverconfig`, holds it);
without it the server behaves as upstream.

## T3 server (Linux, headless)

On a box that runs T3 as a server (`npm install -g t3@nightly` with the `t3code.service`
systemd user service), the patches go into the server itself, so every client that connects
to it (desktop, web, phone) gets them.

```sh
t3code-customize server          build for the version the service runs, switch to it, restart
t3code-customize server-off      put the stock server back and restart
t3code-customize autoupdate on   rebuild when T3 switches versions, and nightly at 04:30
t3code-customize status          server version, customized or not, background updates
```

It reads the active version from `~/.t3/runtime/service-state.json`, builds the patched
binary and web client from the tag `v<version>` (with the Node upstream embeds, as its
release workflow does), and swaps them into `~/.t3/runtime/versions/<version>/`. The
originals stay beside them as `t3.stock` and `client.stock`. After the restart it waits
for the service to answer on port 3773; if it does not, it puts stock back and restarts
again. A new T3 version (from `t3 update` or any other installer) lands in a new folder,
so it runs stock until the rebuild, which `autoupdate on` starts as soon as T3 switches.

## Machines (fleet)

`machines.json` lists every machine that runs T3 with these patches: `kind` is `mac` (app
plus its built-in server) or `server` (headless Linux), `hostname` is how a machine
recognizes itself, `ssh` the aliases to try from the others, `fix` the agent of the one machine
that ports (the porter, see [docs/machines.md](docs/machines.md)) and `ios` the Mac that builds the
iOS app.

```sh
t3code-customize fleet                 update every machine at once
t3code-customize fleet --only devbox1  just one
```

It runs from any machine on the list. Each other machine first gets this repo's files
(Syncthing usually brings them; otherwise they are copied over SSH), then runs `update`
(Mac) or `server` (Linux) in its login shell. A summary shows per machine: ok, needs a
port, or failed. Run it after every change to this repo; the background updaters on each
machine pick changes up on their own within the hour (Mac) or night (server).

### A new machine

1. Install stock T3 Code Nightly: the app on a Mac, or `npm install -g t3@nightly` and its
   service on a Linux server (`t3 service install`, then `t3 connect` to link it).
2. Make sure the other machines reach it over SSH without a prompt, and that it has git and
   Python 3.
3. Add it to `machines.json`, commit and push.
4. From any machine: `t3code-customize fleet --only <name>`, then on the new machine
   `t3code-customize autoupdate on`.

## How it works

T3 Code is open source (MIT). This repo holds patch layers and one script:

| Folder | What | Applied by |
| --- | --- | --- |
| `patches/` | Stats for nerds, shared with upstream | every build |
| `patches-port/` | this fork's port of `patches/` while upstream lags behind a nightly | every build, instead of `patches/` |
| `patches-tt/` | own changes to T3 Code | every build |
| `patches-ios/` | changes only the iOS app needs | `t3code-customize ios` |

The script:

1. reads your installed T3 Code (Mac app, AppImage or server): its exact upstream commit and the public config T3 Connect needs,
2. applies the layers to that commit and runs their tests, typechecks and upstream's lint (`checks*.json`),
3. rebuilds the web, server and desktop JavaScript (or the iOS app),
4. on Linux and Windows, lays it over a copy of your app, keeping every native part as shipped, and checks the result byte for byte; on a server, swaps the rebuilt `t3` and web client into T3's runtime folder.

On macOS nothing is copied or re-signed, so your app keeps its signature, keychain access, passkeys and T3's own updates. The launcher opens your own `T3 Code (Nightly).app` with a startup hook, loads the rebuilt bundles into it before any app code runs, and closes the hook again. Opening T3 Code any other way (Dock, Finder, a `t3code://` link) gives you stock.

Everything runs on your machine. Your installed app and your T3 data are never modified by the
build. The customized app uses the same T3 profile as stock; quit stock before switching.

## Commands

```
t3code-customize             update the patches and build for the T3 Code installed now
t3code-customize status      show what the next launch opens
t3code-customize autoupdate  macOS and server: keep everything up to date in the background
t3code-customize server      Linux T3 server: build the patches into the server the service runs
t3code-customize fleet       update every machine in machines.json
t3code-customize port        port every patch layer onto a nightly (one agent session; the porter)
t3code-customize continue    after resolving a conflict: finish that stage, apply the next
t3code-customize checks      run the tests, typechecks and lint of the applied patches
t3code-customize ios         macOS: build the patched iOS app and upload it to TestFlight
t3code-customize off | on    switch between stock and the customized build
t3code-customize uninstall   remove it, its launcher, builds and caches
```

## Good to know

- **Bugs:** before reporting anything to T3 Code, run `t3code-customize off`, reopen and check it happens on stock too. Report customization problems here.
- **macOS:** the customization applies when T3 Code starts from the launcher. If T3 Code is already running, the launcher just brings it forward. It relies on T3 Code allowing a startup hook (`--inspect-brk`); if a release turns that off, the build stops and says so.
- **Windows signatures:** updating embedded archive hashes changes the copied
  executable, so it no longer has the official Authenticode signature. This is
  a local customized copy, not a signed distributable installer.
- **Windows WSL environments:** this version patches the native Windows server.
  The embedded WSL runtime archive stays stock; stats additions on WSL-hosted
  threads are not supported by this adaptation yet.
- **Fork:** with an `upstream` remote, every run merges newer work from [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize) when it merges cleanly. Each own change, its checks and its intent are listed under "Fork changes" in [AGENTS.md](AGENTS.md).
- **Architectures:** the private Node downloader supports x64 and arm64.
  Build on the same platform and architecture as the installed app; this is
  not a cross-compilation tool.
- **Files on Linux and macOS:** data/builds in `~/.local/share/t3code-customize`,
  source/logs in `~/.cache/t3code-customize`.
- **Files on Windows:** data/builds in `%LOCALAPPDATA%\t3code-customize`,
  source/logs in its `cache` subdirectory.

## Development checks

```sh
python -m unittest discover -s tests -v
python t3code-customize verify
```

Use `python3` on Linux. The first command tests layouts, split/merged
archives, update fallback, locks, command shims and integrity metadata with
fixtures. Windows also exercises the real PE resource API. The second command
applies all patches to their base and runs every test and typecheck in
`checks.json`; it downloads upstream sources and dependencies.

CI runs the platform tests on Linux, macOS and Windows, plus upstream patch
verification on Linux and macOS. Fixture tests are separate from real desktop startup
and provider integration checks.

## Credits

- **[Tyler South](https://github.com/btsouth)** wrote [t3code-customize](https://github.com/btsouth/t3code-customize): the build script, the Linux AppImage build and the Stats for nerds and usage-limit patches this fork builds on.
- **[T3 Tools](https://github.com/pingdotgg/t3code)** makes T3 Code. The worktree handoff fix ports upstream PR [#15203](https://github.com/pingdotgg/t3code/pull/15203); the child-thread server side follows PR [#16699](https://github.com/pingdotgg/t3code/pull/16699).
- **[asc-cli](https://github.com/tddworks/asc-cli)** by tddworks uploads the iOS build to TestFlight.

## License

MIT, same as T3 Code. Copyright (c) 2026 Tyler South; see [LICENSE](LICENSE).
