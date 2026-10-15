# Porting the patches to a new T3 Code nightly

These instructions are for a coding agent. A person can follow them too.

The patches in `patches/` are commits made against the upstream commit in
`patches/base.txt`. Upstream moves fast, so they often stop applying cleanly. Your job
is to carry them onto the user's nightly with every feature still working.

## Start

1. Run `./t3code-customize build` from this repo. It finds the installed AppImage,
   reads the exact upstream commit it was built from, and applies the patches to
   that commit in the source checkout at `~/.cache/t3code-customize/t3code`.
2. If it reports a conflict, a rebase is stopped in that checkout. If it reports a
   failing test or typecheck, the commits are in place and the checks failed.

## Fix

Work only in `~/.cache/t3code-customize/t3code` and this repo.

- Conflicts: resolve each file, `git add` it, then `GIT_EDITOR=true git rebase --continue`.
  Keep upstream's change and port the patch on top of it. When upstream moved or split
  a file, carry the change to the new location and follow the new APIs.
- Failing checks: fix the relevant commit with `git commit --fixup=<sha>`, then
  `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <nightly commit>`. Keep one
  commit per patch.
- If a test file moved upstream, update its path in `checks.json`.
- `git log <base>..<nightly commit>` and `git show` explain what changed upstream.
- To install dependencies, use exactly `pnpm install --frozen-lockfile --ignore-scripts`
  in the source checkout, the same as the tool.

Do not drop a patch, delete or weaken a test, or skip a check to get green. If a
feature can't be ported sensibly, stop and explain why.

## Finish

If `t3code-customize` started you, stop once the tests and typechecks in `checks.json`
pass (run them from the source checkout with `node_modules/.bin/vp test run <files>` and
`node_modules/.bin/tsc --noEmit -p <package>/tsconfig.json`). It continues the build itself.

Otherwise run `./t3code-customize build --resume`. It reruns the checks on the checkout as you
left it, builds, installs the result and writes the ported commits back to
`patches/`. Leave the checkout clean with no rebase in progress.

End with a short report: what changed upstream, what you changed and in which files,
and whether the final build succeeded.

## Fork changes

This repo is Tim's fork of [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize).
Every update must carry the fork's own changes forward, and an agent must confirm that
upstream did not break or duplicate them. This section says how.

### Ownership

| Upstream owns (never commit changes) | The fork owns (commit changes) |
| --- | --- |
| `patches/*.patch`, `patches/base.txt`, `checks.json` | `patches-tt/*.patch`, `checks-tt.json`, this section |
| the Linux code paths in `t3code-customize` | macOS and update code in `t3code-customize`, `README.md` macOS section |

- A port of the shared patches in `patches/` stays uncommitted. Upstream's next port replaces
  it; the tool keeps a backup in `~/.local/share/t3code-customize/patches.bak-*`.
- Every change to T3 Code itself is one commit in `patches-tt/`, with its tests in
  `checks-tt.json` and a row in the table below. Never fold it into a shared patch.

### Porting own patches

The tool applies the shared patches, rebases them onto the nightly, then applies
`patches-tt/` with `git am --3way`. When an own patch conflicts, a `git am` is stopped in
the source checkout: resolve each file, `git add` it, then `git am --continue`. Keep
upstream's change and carry the intent from the table onto it. The rules in "Fix" above
apply (one commit per patch, no weakened tests).

### Checking that an update did not break a fork change

After every port, upstream merge or nightly that touches files in the table, and before
reporting done:

1. For each row, read what upstream changed in its files:
   `git -C ~/.cache/t3code-customize/t3code log -p <previous nightly>..<new nightly> -- <files>`.
2. Confirm the intent still holds on the new code. If upstream now does the same thing
   itself, stop and propose dropping the own patch rather than applying both.
3. Run the checks (`checks.json` plus `checks-tt.json`; the tool runs both) and the row's
   check.
4. Commit a changed `patches-tt/` as `chore: port own patches to nightly <version>`.
5. Report per row: unaffected, ported (what changed), or needs a decision.

When upstream changes `t3code-customize`, merge it by hand if `pull_latest` could not:
keep every `MAC` branch and the `update`, `autoupdate`, `install-pending` and own-patch
code, then run `python3 -m py_compile t3code-customize` and `./t3code-customize status`.

### Fork changes and their checks

| Change | Files | Intent | Check |
| --- | --- | --- | --- |
| Claude context window (`patches-tt/0001`) | `apps/server/src/orchestration-v2/Adapters/ClaudeAdapterV2.ts`, `apps/server/src/provider/Drivers/ClaudeSkills.ts`, `apps/web/src/components/chat/ComposerStats.logic.ts` | Claude context is measured against the smaller of the model window and `autoCompactWindow` (T3's "Auto-compact after", else Claude's user, project and local settings files, read once per session, as the CLI does). Label "Managed by Claude". | Tests in `checks-tt.json`. In the app, with `"autoCompactWindow": 300000` in `~/.claude/settings.json`, the context popover shows a window of 300,000. |
| macOS build | `t3code-customize` (`find_mac_app`, `finish_mac_app`, `stage_mac_build`, `install_pending`) | Copy of the installed `.app` at `~/Applications/T3 Code (Customized).app`: rebuilt `app.asar`, matching `ElectronAsarIntegrity`, `T3CODE_DISABLE_AUTO_UPDATE` in `LSEnvironment`, ad-hoc signature. Swapped in only while closed. | `./t3code-customize status`; `codesign --verify --deep --strict` on the copy. |
| macOS updates | `t3code-customize` (`update_stock`, `cmd_update`, `cmd_autoupdate`, `cmd_install_pending`) | Installs newer releases the way T3's updater does: feed from the app's `app-update.yml`, a zip T3 already downloaded when it matches, sha512 from the feed, the installed app's designated requirement, swap only while closed. | `./t3code-customize` reports "Already up to date" or installs; a foreign or ad-hoc signed app must fail the requirement check. |
| Upstream merge | `t3code-customize` (`pull_latest`) | Each run merges `upstream/main` when it merges cleanly, else continues with the patches it has. | `git log upstream/main..HEAD` shows only fork commits after a run. |
