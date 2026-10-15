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
| `patches/*.patch`, `patches/base.txt`, `checks.json` | `patches-port/`, `patches-tt/`, `checks-tt.json`, this section, `CLAUDE.md` |
| the Linux code paths in `t3code-customize` | macOS, update, server and fleet code in `t3code-customize`, `machines.json`, the `README.md` macOS, server and machines sections |

- A port of the shared patches goes to `patches-port/` (with its own `base.txt`), never to
  `patches/`; the tool writes it there. Builds use it while it targets a newer nightly than
  `patches/base.txt`. Once upstream catches up, the tool says `patches-port/` is unused:
  delete it in a commit.
- Every change to T3 Code itself is one commit in `patches-tt/`, with its tests in
  `checks-tt.json` and a row in the table below. Never fold it into a shared patch.

### Machines

Tim runs T3 on every machine in `machines.json`: the MacBook Pro and MacBook Air (app plus
built-in server, `kind: mac`) and devbox1 (headless server, `kind: server`). All of them
run the same patches.

- **After every change to this repo** (script, `patches-*`, checks) that is committed and
  pushed, run `./t3code-customize fleet` and report the summary per machine. It restarts
  devbox1's T3 server, which reconnects open sessions; say so when you report.
- **A new machine:** follow "A new machine" in `README.md`. A new Linux box is first set up
  with `~/Devops/Personal/playbook-new-box`; this repo only adds the patches.
- Never edit a machine's T3 install by hand; `server`, `server-off` and `update` own it.
- Python must stay compatible with macOS's system Python 3.9.

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
   For a row that ports an upstream PR, run
   `gh pr view <n> --repo pingdotgg/t3code --json state,headRefOid`. MERGED and in the
   installed nightly on every machine: delete the patch, its checks and its row. Head
   differs from the ported head in the row: port the new commits
   (`gh pr diff <n> --repo pingdotgg/t3code --patch`) and update the head. CLOSED
   unmerged: report it and ask whether to keep the patch.
3. Run the checks (`checks.json` plus `checks-tt.json`; the tool runs both) and the row's
   check.
4. Commit changed `patches-port/` and `patches-tt/` as `chore: port patches to nightly <version>`.
5. Report per row: unaffected, ported (what changed), or needs a decision.

When upstream changes `t3code-customize`, merge it by hand if `pull_latest` could not:
keep every `MAC` branch and the `update`, `autoupdate`, `install-pending` and own-patch
code, then run `python3 -m py_compile t3code-customize` and `./t3code-customize status`.

### Fork changes and their checks

| Change | Files | Intent | Check |
| --- | --- | --- | --- |
| Claude context window (`patches-tt/0001`) | `apps/server/src/orchestration-v2/Adapters/ClaudeAdapterV2.ts`, `apps/server/src/provider/Drivers/ClaudeSkills.ts`, `apps/web/src/components/chat/ComposerStats.logic.ts` | Claude context is measured against the smaller of the model window and `autoCompactWindow` (T3's "Auto-compact after", else Claude's user, project and local settings files, read once per session, as the CLI does). Label "Managed by Claude". | Tests in `checks-tt.json`. In the app, with `"autoCompactWindow": 300000` in `~/.claude/settings.json`, the context popover shows a window of 300,000. |
| Worktree handoff continuation (`patches-tt/0002`) | `apps/server/src/mcp/WorktreeMcpService.ts`, `apps/server/src/orchestration-v2/{Orchestrator,RunExecutionService,ProviderSessionManager,EffectOutbox,EffectWorker}.ts`, `packages/contracts/src/orchestrationV2.ts`, `packages/provider-core/src/server/ProviderAdapter.ts` | Port of upstream PR pingdotgg/t3code#15203 (fixes #15136): after `t3_worktree_handoff` the continuation prompt starts instead of "Provider event stream closed unexpectedly". Drop this patch once `gh pr view 15203 --repo pingdotgg/t3code --json state` says MERGED and that nightly is installed everywhere; then restore the handoff note in `~/.agents/rules/t3-code.md`. | Tests in `checks-tt.json`. In T3, a thread on the project root calls `t3_worktree_handoff` with a `continuationPrompt` and continues in the worktree. |
| Child threads (`patches-tt/0003`) | `packages/contracts/src/orchestrationV2.ts`, `apps/server/src/orchestration-v2/{Orchestrator,ProjectionStore,ThreadLaunchService,ThreadManagementService}.ts`, `apps/server/src/mcp/{OrchestratorMcpService.ts,toolkits/project/handlers.ts}`, `packages/client-runtime/src/state/{models,threadCommands}.ts`, `apps/web/src/components/{Sidebar.tsx,Sidebar.families.ts,threadActionMenu.logic.ts}`, `apps/web/src/contextMenuFallback.ts` | Server side of upstream PR pingdotgg/t3code#16699: `t3_thread_launch` and `create_threads` record `openedByThreadId`. The sidebar nests a child under its opener as in Claude.app (guide line, no favicon) when both sit in the same section. The server records `settledBy` (`agent` for T3 tools, `auto` for automatic settlement; absent for a user settle). A child an agent or auto-settle settled stays under an opener that is still pinned, active or working; a child Tim settles himself goes to Settled; a live child under a settled opener stays in its own section. Context menu "Hide/Show child threads"; collapsed, only children needing input or approval and the open thread stay, the rest become a stub "N child threads · x failed · y new · z working". Older threads stay flat. If upstream ships its own child-thread sidebar (#16699 web side or #15988), propose dropping this patch. | Tests in `checks-tt.json`. In T3, a thread that calls `t3_thread_launch` shows the new thread nested under it while both are in the same section. |
| macOS build | `t3code-customize` (`find_mac_app`, `finish_mac_app`, `stage_mac_build`, `install_pending`) | Copy of the installed `.app` at `~/Applications/T3 Code (Customized).app`: rebuilt `app.asar`, matching `ElectronAsarIntegrity`, `T3CODE_DISABLE_AUTO_UPDATE` in `LSEnvironment`, signed with this Mac's self-signed identity (`signing_identity`, keychain `~/.config/t3code-customize/signing.keychain-db`) so keychain "Always Allow" survives rebuilds; ad hoc only as fallback. Swapped in only while closed. | `./t3code-customize status`; `codesign --verify --deep --strict` on the copy; `codesign -d -r-` shows `certificate leaf = H"…"`, not a cdhash. |
| macOS updates | `t3code-customize` (`update_stock`, `cmd_update`, `cmd_autoupdate`, `cmd_install_pending`) | Installs newer releases the way T3's updater does: feed from the app's `app-update.yml`, a zip T3 already downloaded when it matches, sha512 from the feed, the installed app's designated requirement, swap only while closed. | `./t3code-customize` reports "Already up to date" or installs; a foreign or ad-hoc signed app must fail the requirement check. |
| T3 server | `t3code-customize` (`cmd_server`, `build_server`, `install_server_build`, `restart_server`, `server_autoupdate`) | Patched `t3` and `client/` in `~/.t3/runtime/versions/<active>/`, built from tag `v<version>` with `VP_NODE_VERSION` = upstream's `SEA_NODE_VERSION`; originals kept as `*.stock`; health check on port 3773 or back to stock. Depends on upstream's `apps/server/scripts/cli.ts build-exe` and the runtime layout. | `./t3code-customize status` on devbox1 shows "Customized: yes"; `curl` on port 3773 gives 200; `t3 connect status --json` is still linked. |
| Fleet | `t3code-customize` (`cmd_fleet`, `sync_repo`), `machines.json` | One command updates every machine from any machine; files arrive by Syncthing or SSH copy, identical script and recipe hash required before building. | `./t3code-customize fleet` ends with every machine `ok`. |
| Hermetic checks | `t3code-customize` (`checks`) | Tests and typechecks run with `HOME` set to an empty temp dir, as in upstream's CI. Upstream's ClaudeAdapterV2 steer test "(never answers)" reads the real `~/.claude/skills` mid-steer and hangs once there are many skills (devbox1, 73). | `./t3code-customize build --resume` passes the checks on devbox1. |
| Upstream merge | `t3code-customize` (`pull_latest`) | Each run merges `upstream/main` when it merges cleanly, else continues with the patches it has. | `git log upstream/main..HEAD` shows only fork commits after a run. |

## Agent skills

### Issue tracker

GitHub Issues on the fork `timvdhoorn/t3code-customize-tt`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created when needed. See `docs/agents/domain.md`.
