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
- **Fleet keeps each checkout on git.** It works on the main checkout's path on every machine
  (`~/Devops/Personal/t3code-customize-tt`, `checkout_root`), also when it runs from a git worktree,
  and never creates a missing checkout. It never copies files into a machine's git checkout: there it
  runs `git fetch` (or sends `origin/main` as a `git bundle` over SSH when that machine cannot reach
  GitHub) and fast-forwards `main` to `origin/main`. Files an older fleet copied in (identical to
  `origin/main`) are reset to it; untracked files `origin/main` does not have (a checkout's own
  installed skills) stay and do not count. A change that differs from `origin/main` (an untracked
  file included), local commits or another branch stop that machine (`left its checkout alone: ...`)
  and stay as they are: commit, push or discard them there, then rerun fleet. Each Mac ends on
  `## main...origin/main` with nothing changed, so its hourly `pull_latest` keeps working. A fleet run from a branch or a dirty
  checkout still moves the machines to `origin/main` and says so.
- **A Mac updates through its LaunchAgent.** Over SSH fleet turns `autoupdate on`, then starts that
  LaunchAgent once (`launchctl kickstart gui/<uid>/com.github.t3code-customize.update`, after a run
  that holds it or the checkout has finished, up to `--wait-lock` minutes), prints the new lines of
  `~/.cache/t3code-customize/logs/autoupdate.log` and reports the run's exit code. The run lives in
  the login session, so on the MacBook Pro the iOS build it may start can sign: from an SSH session
  codesign fails with `errSecInternalComponent` after the whole build. `ios` itself stops at once when
  `security show-keychain-info` fails (any SSH session) and names that kickstart. `--force` and
  `--fix` first rebuild directly over SSH; that path never builds iOS. The agent runs at `ProcessType`
  Interactive with `Nice` 10: as Standard its browser checks ran at priority 20 and failed under load
  ("Unattended updates" in [fork-changes.md](fork-changes.md)).
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
    one and installs it when Tim quits the app (`patches-tt/0005`); nothing restarts the app for
    it. It does this only for a nightly the patches cover: it reads `covered-nightly.txt` from
    `main` of this repo (the port export writes it, the port PR carries it) and leaves a newer nightly
    alone, also when the lookup fails, until a merged port covers it, so the launcher never opens
    stock for lack of patches. A click on "Download" or "Restart to update" in Settings is not
    gated. The install changes the app's `Info.plist`, the `autoupdate` LaunchAgent rebuilds the
    overlay, and the next launcher start loads it (opened before that, it opens stock and starts the
    rebuild). On the MacBook Pro (`"ios": true`) the same run then builds the iOS app for the new
    nightly and uploads it to TestFlight. It does the same when only the patches changed under the
    same nightly (a merged `patches-ios/` fix, say): the desktop says "Already up to date" and stays
    as it is, and iOS builds because `ios-state.json` records another patch recipe (`ios_behind`;
    `status` then says `behind`). So after such a merge, `fleet` (which kickstarts that LaunchAgent)
    is all it takes. When the patches do not fit the new nightly, the run
    notifies Tim and stays on its current build (see "Ports" below). A re-signed copy at `~/Applications/T3 Code (Customized).app`
    from older versions of this tool ran with `T3CODE_DISABLE_AUTO_UPDATE=true`, so it never
    updated; `install_mac_launcher` removes it, and none may remain.
  - devbox1: the `autoupdate` timer at 04:30 runs `server --t3-update`: `t3 update`
    stages the newest `t3@nightly` (a no-op when it already runs it), the customized server is built
    for it, and the one restart waits for idle as above. When the patches break there, it notifies
    and keeps its current build.
- **Ports.** No machine ports unattended and no run starts an agent (Tim's decision, 2026-11-06:
  the unattended agent ports kept failing). No machine in `machines.json` has `"fix"`, so no run
  hands a port off, and `fleet` turns `autoupdate on` without `--fix`. A run that hits a conflict or
  failing check aborts its rebase or `git am`, notifies, and leaves its checkout clean and its app
  untouched. Tim then starts a thread in this repo on devbox1 (16 cores; the MacBook Pro ran out of
  memory on checks) and ports with that agent, per `.agents/playbooks/update.md` and
  `docs/porting.md`; the port goes through a normal PR.
- **A nightly older than the patches** (the Mac still on the nightly before a port merged) builds
  with the patch set from git history made for exactly that nightly, or waits for the app update
  and exits 0. It never leaves a stopped rebase or `git am`; an unattended run that finds one an
  unattended run left, untouched since, aborts it (`continue`, `checks` or `--resume` claim it).
- **Asked to update** ("update", "zijn er updates", "update alles"): follow
  [`.agents/playbooks/update.md`](../.agents/playbooks/update.md).
- **A new machine:** follow "A new machine" in [README.md](../README.md). A new Linux box is first set up
  with `~/Devops/Personal/playbook-new-box`; this repo only adds the patches.
- Never edit a machine's T3 install by hand; `server`, `server-off` and `update` own it. On a Mac,
  T3's own updater installs new releases (up to the covered nightly, `covered-nightly.txt`) into the
  untouched app; `update` (and `autoupdate`) only rebuild the overlay for it, and until then the launcher opens stock.
- Python must stay compatible with macOS's system Python 3.9.

## Unattended ports

Unused since 2026-11-06 (see "Ports" above): it applies only if `--fix` is passed again by hand.

Tim's standing grant (retro of 2026-10-16): when `--fix <agent>` ported the patches without him,
`publish_port` commits the port to the branch `port/nightly-<version>`, pushes it and opens a PR
against `main`. It merges that PR (squash) and starts `fleet`, without asking, only when both hold:

1. every test, typecheck and lint in `checks.json` and `checks-*.json` that the run applies passed
   (the port did not run with `--skip-checks`, which blocks the grant). The tool trusts the stamp
   `checks` writes (`t3code-customize-checks.json` in the checkout's git dir: HEAD, nightly, check
   lists and `recipe_hash()`, which ignores operational code in the script: see "Recipe hash" in
   `docs/fork-changes.md`, and it covers `known-upstream-failures.json`); a run that finds it
   current skips the checks. A known upstream failure counts as passed (see below), and
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
   `base.txt` files of the patch folders and `covered-nightly.txt` (a changed check list goes along, for review).

The run publishes the port right after exporting it, before it waits for idle threads, so a
deferred or failed restart never loses it. A `port/nightly-<version>` branch that holds commits
the tool did not make is left alone; the port goes to `-2`, `-3` and so on. After a merge it starts
`fleet --wait-lock 180` detached, which waits for the run that merged (an iOS build may follow).
Only a machine with git and `gh` can publish: the porter, devbox1. A port that does not qualify
leaves its PR open (`status` lists it under "Open PRs") and notifies Tim. The grant covers
exactly this case. An agent porting by hand follows the normal PR flow.

### Known upstream failures

An upstream test that fails on the plain nightly would stop every `checks`, `server`, `port` and
04:30 run, and with it the grant, until upstream fixes it. `known-upstream-failures.json` (fork-owned)
lists such tests: `file`, `test` (the full name, `describe > ... > test`), `upstream` (PR or issue
URL) and `added`. A failing vitest step passes only when every failed test in its JSON report matches
an entry exactly by file and full name, its file has no load error and no case in an unusual state,
no suite or hook failed in the step (`Failed Suites` in vitest's output: a throwing `beforeAll`
skips the tests under it), and the test is upstream's: the case's own source (its `it(`/`test(`
line to its closer at the same indentation: `});`, `}, 10_000);`, or `);` for an expression-bodied case; lines inside a
template literal (strings and comments skipped) never count as the closer) is identical
at the nightly commit and at HEAD, so a patch that edits the test voids the entry. Any other failure,
an unhandled error or a non-zero exit without a parsable report still fails. Each tolerated test
prints `pass (known upstream failure: <name>)`.

The proof that a listed test fails without patches is the run on the plain nightly made before
adding it (rerunning it there in every check would cost a second install); the source check keeps a
patch from rewriting the test itself. A patch that changes the code under test is not caught by it,
so add an entry only after that plain-nightly run, with the upstream reference. `checks` records
per entry whether it failed or passed (`~/.cache/t3code-customize/known-upstream-failures-seen.json`);
`status` lists the entries and calls one stale once it passed on any nightly; from then on it is no
longer tolerated, so remove it.
