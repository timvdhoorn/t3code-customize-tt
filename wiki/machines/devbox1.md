# devbox1

> Source: `./t3code-customize status`; `systemctl --user list-timers --all | rg t3`; `journalctl --user -u t3code-customize-server.service -u t3code-customize-server-run -u t3code-customize-fleet`
> Updated: 2026-11-14

The Linux T3 server (`"kind": "server"` in `machines.json`). It runs the customized `t3` and web client from `~/.t3/runtime/versions/<active>/`, with the originals kept as `*.stock`, and is where ports run.

## Units
- `t3code-customize-server.timer`: daily 05:30 CET, runs `server --background --t3-update --wait-lock 30` (stages the newest nightly, rebuilds, restarts only when no thread works).
- `t3code-customize-server-run`: the detached unit a `server` run started from a T3 agent uses.
- `t3code-customize-fleet`: the detached unit `fleet` uses from a T3 agent; read its journal in a later turn.
- `t3-nightly-check.timer`: daily 04:17 CET, reports the nightly pin.

## Shared checkout and lock
- `~/.cache/t3code-customize/t3code` belongs to the run holding `~/.cache/t3code-customize/lock` (the file names the holder).
- `.git/t3code-customize-run.json` in the checkout records the run that stopped there.
- An unattended run aborts a stop only when its run is gone, nobody claimed it and `unattended` was true.
- A stop left by a manual run (`"unattended": false`) blocks every nightly server build until someone aborts or finishes it.
- Ports work in their own detached worktree under `~/.cache/t3code-customize/wt/`, never in the shared checkout.

## Server build check
- The web client and the executable must hold a marker from `skip-shared.json` (`server_build_markers`).
- The default marker `statsForNerds` comes from a left-out shared patch, so it alone would fail the build.
- A restart waits until no thread works on this server (`busy_threads`); the journal lists the busy threads each minute.
