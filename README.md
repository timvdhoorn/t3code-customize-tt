# t3code-customize

Your 5 hour and weekly usage, context and tokens per second, right under the T3 Code composer.

Unofficial. Not affiliated with T3 Tools. For T3 Code Nightly on Linux (AppImage) and macOS.

## What you get

- **Usage meters** for your 5 hour and weekly limits, from the limits T3 already gets from your providers.
- **Context** used in the thread. Hover it for the window size, the auto-compaction threshold and a Compact now button.
- **Tokens per second** for the last response, with turn time and token details on hover. Claude rates are measured from the stream; Codex rates are labeled approximate.
- **Cache rate** for the last turn.

Everything else is stock T3 Code, including T3 Connect and the mobile app.

## Install

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/timvdhoorn/t3code-customize-tt/main/install.sh)"
```

Or clone it anywhere and run `./t3code-customize`.

The first run downloads T3 Code's source and build tools, so give it 5 to 15 minutes. Then quit T3 Code fully, open **T3 Code (Customized)** from your app launcher and turn on **Settings > General > Stats for nerds**.

You need git and Python 3. If your Node is older than 24, it fetches its own copy. It uses about 6 GB of disk. If your AppImage isn't in `~/Applications` or `~/Downloads`, run it once with `--appimage /path/to/T3-Code.AppImage`.

## After every T3 Code update

```sh
t3code-customize
```

That's it. It pulls the latest patches, rebuilds for your new version and tells you when to reopen. Until you run it, the launcher opens stock T3 Code and tells you why.

## When a nightly breaks the patches

Upstream moves fast, and sometimes a nightly changes the code the patches touch. When that happens:

- If you have Claude Code or Codex installed, it offers to port the patches for you right there.
- Otherwise, wait a bit: this repo usually catches up within a day. Then run `t3code-customize` again.
- Or point any coding agent at this repo and ask it to follow [AGENTS.md](AGENTS.md).

Your current T3 Code keeps working the whole time.

## macOS

The customized build is a copy of your app at `~/Applications/T3 Code (Customized).app`, signed
for your Mac only. Keep using it as your T3 Code; leave the stock app installed.

```sh
t3code-customize                 install a newer Nightly if there is one, then rebuild
t3code-customize autoupdate on   do that every hour in the background (LaunchAgent)
t3code-customize status          versions, pending build, background updates
```

The copy cannot update itself (Squirrel only accepts T3's own signature), so the tool takes
over that part of T3's updater: it reads the feed from your app's `app-update.yml`, reuses an
update T3 already downloaded, checks the sha512 from the feed, and only installs an app that
satisfies your installed app's code signing requirement, like Squirrel does. Stock is
replaced only while it is closed; a new customized build waits until you quit the customized
app and is swapped in on the next run.

With `autoupdate on --fix claude`, Claude Code ports the patches unattended when a nightly
breaks them. Without it you get a notification and run `t3code-customize --fix claude` yourself.

Differences from stock: passkey sign-in (needs T3's Apple team entitlements) is unavailable,
and macOS asks once for keychain and privacy permissions because the signature differs.
Choose **Always Allow**: the copy is signed with a certificate made for your Mac on the
first build (in a keychain of its own at `~/.config/t3code-customize/signing.keychain-db`),
so the answer holds for every later build.

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
recognizes itself, `ssh` the aliases to try from the others.

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

T3 Code is open source (MIT). This repo holds three patches and one script. The script:

1. reads your installed AppImage: its exact upstream commit and the public config T3 Connect needs,
2. applies the patches to that commit and runs their tests,
3. rebuilds the web, server and desktop JavaScript,
4. lays it over a copy of your app, keeping every native part as shipped, and checks the result byte for byte.

Everything runs on your machine. Your AppImage and your T3 data are never modified.

## Commands

```
t3code-customize             update the patches and build for your installed T3 Code
t3code-customize status      show what the next launch opens
t3code-customize off | on    switch between stock and the customized build
t3code-customize uninstall   remove it, its launcher, builds and caches
```

## Good to know

- **Bugs:** before reporting anything to T3 Code, run `t3code-customize off`, reopen and check it happens on stock too. Report customization problems here.
- **Windows:** not supported yet. The patches are platform independent; only the packaging differs.
- **Fork:** this is a fork of [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize). With an `upstream` remote, every run merges newer patches from there when they merge cleanly. Own changes to T3 Code live in `patches-tt/` (checks in `checks-tt.json`) and go on top of the shared patches; ports of the shared patches go to `patches-port/` until upstream catches up; see "Fork changes" in [AGENTS.md](AGENTS.md).
- **Files:** builds live in `~/.local/share/t3code-customize`, the source checkout and logs in `~/.cache/t3code-customize`.

## License

MIT, same as T3 Code.
