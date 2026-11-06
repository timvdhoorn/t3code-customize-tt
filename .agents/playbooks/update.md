---
when: Tim wants T3 Code updated or asks whether there are updates ("update", "zijn er updates", "update alles", "update T3").
extends:
---

# Update T3 Code everywhere

Bring every machine in `machines.json` and the iOS app on TestFlight to the newest T3 nightly
with the patches. Never interrupt a running thread, and never ask Tim to click what the tooling
can do. [docs/machines.md](../../docs/machines.md) holds the rules (ports, the idle gate); this is the order.

1. Status per machine. Run `./t3code-customize status` here and over SSH on each other machine
   (`ssh <alias> 'exec "$SHELL" -lc "python3 ~/<repo path>/t3code-customize status"'`, aliases in
   `machines.json`). Compare with the newest nightly: `gh release list --repo pingdotgg/t3code
   --limit 5` (desktop) and `npm view t3@nightly version` (devbox1). Note the ported-PR lines
   `status` prints and act on them per "Checking an update" in `docs/fork-changes.md`. `status` also
   lists the repo's open PRs: report each one, a port or feature waiting there has not shipped.
2. Nothing newer and nothing behind: report that per machine and stop.
3. A Mac whose app is older than the newest nightly gets it from T3's own updater: the customized
   build downloads it itself and installs on quit (`patches-tt/0006`). Do not quit or relaunch the
   app; tell Tim it installs the next time he quits T3 Code, unless he asks you to wait for it.
4. Port when the patches no longer apply: a `build`, `update` or `server` reports a conflict or
   failing check. No agent ports unattended; you port, in this thread, on devbox1. Work in your own
   detached worktree of the shared checkout: `./t3code-customize port --source <worktree> --version
   <nightly> --dry-run`, then the loop in `docs/porting.md` (`continue`, `checks --source`), then
   `port --source <worktree> --version <nightly> --resume` to export and open the PR.
5. Merge after Tim's review of the PR, or when he already asked you to finish ("rond af").
6. Run `./t3code-customize fleet` once the patches on `main` fit the newest nightly. It waits for a
   held lock, stages the newest nightly on devbox1 and restarts its server only when no thread
   works there, and turns `autoupdate on` everywhere (the MacBook Pro with `--ios`).
   Run it in the background and wait on its exit. From a thread on devbox1, `server` detaches into
   its own unit that waits for your turn to end: do not wait on that unit in the same turn; end the
   turn and read `journalctl --user -u t3code-customize-server-run` in a later one.
   `deferred: threads busy` is a valid result: report which threads, do not interrupt them.
7. iOS: on the MacBook Pro run `./t3code-customize ios` when `status` says the iOS app is behind.
   When `status` shows an `App update: ... staged` line, the build waits for that update: it
   installs when Tim quits T3 Code, and `autoupdate --ios` then rebuilds the app and the iOS build.
8. Report per machine (mbp, mba, devbox1, TestFlight): nightly before and after, customized yes or
   no, `deferred` with the busy threads, any PR left open, and what still waits for Tim's quit.
