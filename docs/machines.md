# Machines

Tim runs T3 on every machine in `machines.json`: the MacBook Pro and MacBook Air (app plus
built-in server, `kind: mac`) and devbox1 (headless server, `kind: server`). All of them
run the same patches.

- **After every change to this repo** (script, `patches-*`, checks) that is committed and
  pushed, run `./t3code-customize fleet` and report the summary per machine. It waits for a run
  that holds a machine's checkout (up to 30 min, naming the holder), moves devbox1 to the newest
  nightly, restarts devbox1's T3 server once no thread works there (open sessions reconnect; say so
  when you report) and turns `autoupdate on` on every machine with its `machines.json` settings.
  Run from a T3 agent on devbox1 it reruns itself in the systemd unit `t3code-customize-fleet`
  (one at a time) and returns at once, since its server step waits for that agent's thread too: do
  not wait on it in that turn, check `journalctl --user -u t3code-customize-fleet` later
  (`--foreground` runs it inline). On a Mac it runs inline and says not to wait on it.
- **Never interrupt a running thread.** Nothing in this tool quits or relaunches the Mac app. A
  T3 server restarts only in `server` and `server-off`, once per run, and only while it is idle:
  `busy_threads` finds no live work in `~/.t3/userdata/statev2.sqlite`, by the rules the server
  itself uses to recover work after a restart: a run in `orchestration_v2_projection_runs` that is
  `preparing`, `starting`, `running` or `waiting` (on approval or input), a `queued` run that is not
  held (`queueHeld`), or a provider thread with `pendingBackgroundTasks`. Deleted threads do not
  count; an unreadable database, or a missing one on a machine with a T3 server, counts as busy.
  Everything slow happens first: `t3 update` without `--yes` only stages the new version (no
  terminal, so the service keeps running until its next restart), and the customized server is
  built, copied and probed as `*.customize-new`. Then it releases the checkout lock (nothing after
  that touches the source checkout, so a port or another build need not wait for the idle wait,
  which its own waiting threads would prolong) and checks every minute for up to 4 hours
  (`T3CODE_CUSTOMIZE_IDLE_WAIT_MINUTES`). Staging, the swap and the restart take a short restart
  lock (`~/.cache/t3code-customize/restart-lock`, after the checkout lock, never during an idle
  wait); under it the run swaps only when the service still runs its version and the staged build
  is still its own (`t3.customize-new.json`, removed at the start of every staging and written only
  once the probe passed), else it yields: while a run waits, a newer run may rebuild and stage over it. It swaps the files in
  by renaming, runs `daemon-reload` (the unit `t3 update` rewrote) and checks once more right before
  `systemctl restart`. `server-off` and the owed restart below also wait for idle without the checkout lock. Still busy: it
  stops with `deferred: threads busy` (exit 4, fleet says the same) and restarts nothing; the next run
  tries again. A restart deferred after the swap leaves `~/.t3/runtime/.t3code-customize-restart-pending`,
  and a run that finds the build already installed still restarts (gated) while that marker, or
  T3's own `.restart-pending` for the active version, is there. A failed health check rolls back to stock
  and restarts only while idle; otherwise stock waits on disk for the next restart. Run from a T3
  agent on devbox1 (`inside_t3_agent`: the service's `T3_BOOT_SERVICE_UNIT` in the environment, or a
  cgroup in `app-t3code-agents*.slice` or `t3code.service`), `server` moves itself to a systemd unit, which waits for that agent's turn to
  end, so never wait on that unit in the same turn: end the turn and check
  `journalctl --user -u t3code-customize-server-run` later.
- **How each machine gets a new nightly:**
  - Mac: T3's own updater. In the customized build it downloads a new nightly as soon as it finds
    one and installs it when Tim quits the app (`patches-tt/0007`); nothing restarts the app for
    it. The install changes the app's `Info.plist`, the `autoupdate` LaunchAgent rebuilds the
    overlay, and the next launcher start loads it (opened before that, it opens stock and starts the
    rebuild). On the MacBook Pro (`"ios": true`) the same run then builds the iOS app for the new
    nightly and uploads it to TestFlight. When the patches do not fit the new nightly, the run
    hands the port to the porter (see "The porter" below) and stays on its current build. A re-signed copy at `~/Applications/T3 Code (Customized).app`
    from older versions of this tool ran with `T3CODE_DISABLE_AUTO_UPDATE=true`, so it never
    updated; `install_mac_launcher` removes it, and none may remain.
  - devbox1: the `autoupdate` timer at 04:30 runs `server --t3-update --fix claude`: `t3 update`
    stages the newest `t3@nightly` (a no-op when it already runs it), the customized server is built
    for it, and the one restart waits for idle as above. When the patches break there, devbox1 ports
    them itself (it is the porter).
- **The porter.** One machine ports: the one with `"fix"` in `machines.json`, devbox1 (16 cores,
  idle, with `.git`, `gh` and `claude`). The MacBook Pro ran out of memory on checks (61 min for
  one typecheck under swap), so the Macs never run an agent. An unattended run on another machine
  that hits a conflict or failing check aborts its own rebase or `git am`, starts
  `port --commit <nightly> --version <v> --fix claude --background` on the porter over SSH
  (detached, in the systemd unit `t3code-customize-port-<commit>`; a second start while it runs is a
  no-op, and the porter's lock serialises it with its own runs), notifies "port running on devbox1",
  and leaves its checkout clean and its app untouched. It does not hand the same nightly over again
  for 12 hours, and while the patches stay the same its hourly runs stop before they touch the
  checkout; an unreachable porter is notified once per 12 hours. The porter's own unattended runs
  (`server --fix claude` at 04:30) hand their port to `port` too, so every port carries all three
  layers. A port that waits for review (`ports.json`, or an open `port/nightly-<version>` PR) is not
  ported again by any run. When the one agent session leaves a port unfinished, its run cleans the
  checkout, records `failed` in `ports.json` and notifies. `port` applies all three layers, runs one agent session through every stage and the
  checks (`docs/porting.md`), then publishes as below. The Mac's next hourly run picks the merged port
  up through `pull_latest`.
- **A nightly older than the patches** (the Mac still on the nightly before a port merged) builds
  with the patch set from git history made for exactly that nightly, or waits for the app update
  and exits 0. It never leaves a stopped rebase or `git am`; an unattended run that finds one an
  unattended run left, untouched since, aborts it (`continue`, `checks` or `--resume` claim it).
- **Asked to update** ("update", "zijn er updates", "update alles"): follow
  [`.agents/playbooks/update.md`](../.agents/playbooks/update.md).
- **A new machine:** follow "A new machine" in [README.md](../README.md). A new Linux box is first set up
  with `~/Devops/Personal/playbook-new-box`; this repo only adds the patches.
- Never edit a machine's T3 install by hand; `server`, `server-off` and `update` own it. On a Mac,
  T3's own updater installs new releases into the untouched app; `update` (and `autoupdate`) only
  rebuild the overlay for it, and until then the launcher opens stock.
- Python must stay compatible with macOS's system Python 3.9.

## Unattended ports

Tim's standing grant (retro of 2026-10-16): when `--fix <agent>` ported the patches without him,
`publish_port` commits the port to the branch `port/nightly-<version>`, pushes it and opens a PR
against `main`. It merges that PR (squash) and starts `fleet`, without asking, only when both hold:

1. every test, typecheck and lint in `checks.json` and `checks-*.json` that the run applies passed
   (the port did not run with `--skip-checks`, which blocks the grant). The tool trusts the stamp
   `checks` writes (`t3code-customize-checks.json` in the checkout's git dir: HEAD, nightly, check
   lists and `recipe_hash()`, which ignores operational code in the script: see "Recipe hash" in
   `docs/fork-changes.md`); a run that finds it current skips the checks, and
2. each patch keeps exactly the same code: per patch (shared set, `patches-tt/`, `patches-ios/`,
   matched by number) the files it changes, in order by their `diff --git` path, each with its
   added and removed lines in order, without blank and comment-only lines, are identical to the
   committed ones, and no patch was added or dropped. A comment-only line starts with `//`, is a
   `/*` or `<!--` line that ends its comment or runs on, or a line inside a `/*` block (its `*`
   continuations up to `*/`); `#` is code, and so are `/* x */ code();` and a `*` line outside a block. A patch that changes a binary file or a file mode never qualifies. Only
   context, comments, hunk positions and line numbers moved (`code_unchanged`), and
3. nothing else changed: `checks-tt.json`, `checks-ios.json`, the script and every other file are
   byte-identical to `main`, and the repo was on `main`. Untracked files count only inside the patch
   folders (a checkout's own installed skills or lock files do not). The PR holds only the `*.patch` and
   `base.txt` files of the patch folders (a changed check list goes along, for review).

The run publishes the port right after exporting it, before it waits for idle threads, so a
deferred or failed restart never loses it. A `port/nightly-<version>` branch that holds commits
the tool did not make is left alone; the port goes to `-2`, `-3` and so on. After a merge it starts
`fleet --wait-lock 180` detached, which waits for the run that merged (an iOS build may follow).
Only a machine with git and `gh` can publish: the porter, devbox1. A port that does not qualify
leaves its PR open (`status` lists it under "Open PRs") and notifies Tim. The grant covers
exactly this case. An agent porting by hand follows the normal PR flow.
