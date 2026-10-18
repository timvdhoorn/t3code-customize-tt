# Porting the patches to a new T3 Code nightly

These instructions are for a coding agent. A person can follow them too.

The patches in `patches/` are commits made against the upstream commit in
`patches/base.txt`. Upstream moves fast, so they often stop applying cleanly. Your job
is to carry them onto the user's nightly with every feature still working.

## Start

Every update or port of this fork also runs the upstream check in "Checking that an update did
not break a fork change", step 2, for each row that ports an upstream PR or works around an
upstream issue; `status`, `build`, `update` and `server` print the PRs in `ported-prs.json`.

1. Run `python t3code-customize build` from this repo on Windows, or
   `python3 ./t3code-customize build` on Linux and macOS. It finds the installed
   application (AppImage, macOS app or Windows executable), reads its exact upstream
   commit, and applies the patches in the private source checkout. Use `--app` for a
   nonstandard installed path. The source checkout is `<cache>/t3code`; platform cache
   locations are in [README.md](README.md#good-to-know), and the build prints its log path.
2. If it reports a conflict, a rebase is stopped in that checkout. If it reports a
   failing test or typecheck, the commits are in place and the checks failed.

## Fix

Work only in that private source checkout and this repo.

- Conflicts: resolve each file, `git add` it, then `git -c core.editor=true rebase --continue`.
  Keep upstream's change and port the patch on top of it. When upstream moved or split
  a file, carry the change to the new location and follow the new APIs.
- Failing checks: fix the relevant commit with `git commit --fixup=<sha>`, then
  `git -c sequence.editor=true rebase -i --autosquash <nightly commit>`. Keep one
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

Otherwise run the same Python entry with `build --resume`. It reruns the checks on the checkout as you
left it, builds, installs the result and writes the ported commits back to
`patches/`. Leave the checkout clean with no rebase in progress.

End with a short report: what changed upstream, what you changed and in which files,
and whether the final build succeeded. Separate fixture tests, native process
checks and real desktop startup evidence.

## Fork changes

This repo is Tim's fork of [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize).
Every update must carry the fork's own changes forward, and an agent must confirm that
upstream did not break or duplicate them. This section says how.

**This repo is public.** Never commit secrets or private data: no keys, tokens, passwords,
`.p8` or `.bin` contents, pairing URLs, Tailscale IPs, customer names or log excerpts with
personal data. Name where a secret lives (a 1Password item, a path under
`~/.t3/userdata/secrets/`) instead of its value, and check the staged diff before every commit.

### Ownership

| Upstream owns (never commit changes) | The fork owns (commit changes) |
| --- | --- |
| `patches/*.patch`, `patches/base.txt`, `checks.json` | `patches-port/`, `patches-tt/`, `checks-tt.json`, `patches-ios/`, `checks-ios.json`, `ios.json`, `ported-prs.json`, `.agents/playbooks/`, this section, `CLAUDE.md` |
| the Linux, Windows and macOS build and launch paths in `t3code-customize`, `platform_support.py`, `macos/`, `install.ps1`, `tests/`, `docs/macos.md` | update, autoupdate, server, fleet and ios code in `t3code-customize`, `machines.json`, `tests/test_checkout_guard.py`, `tests/test_unattended_updates.py`, the `README.md` macOS, server and machines sections |

- A port of the shared patches goes to `patches-port/` (with its own `base.txt`), never to
  `patches/`; the tool writes it there. Builds use it while it targets a newer nightly than
  `patches/base.txt`. Once upstream catches up, the tool says `patches-port/` is unused:
  delete it in a commit.
- Every change to T3 Code itself is one commit in `patches-tt/`, with its tests in
  `checks-tt.json` and a row in the table below. Never fold it into a shared patch.
- A change only the iOS app needs is one commit in `patches-ios/`, with its tests in
  `checks-ios.json` and a row below. Only `t3code-customize ios` applies this folder, after
  `patches-tt/`, so the desktop app and the servers never carry it. Moving shared code for iOS
  (into `packages/client-runtime`, say) keeps the old module as a re-export and the old test
  files in place, because `checks-tt.json` still names them.

### Machines

Tim runs T3 on every machine in `machines.json`: the MacBook Pro and MacBook Air (app plus
built-in server, `kind: mac`) and devbox1 (headless server, `kind: server`). All of them
run the same patches.

- **After every change to this repo** (script, `patches-*`, checks) that is committed and
  pushed, run `./t3code-customize fleet` and report the summary per machine. It waits for a run
  that holds a machine's checkout (up to 30 min, naming the holder), moves devbox1 to the newest
  nightly, restarts devbox1's T3 server once no thread works there (open sessions reconnect; say so
  when you report) and turns `autoupdate on` on every machine with its `machines.json` settings.
- **Never interrupt a running thread.** Nothing in this tool quits or relaunches the Mac app. A
  T3 server restarts only in `server` and `server-off`, once per run, and only while it is idle:
  `busy_threads` finds no live work in `~/.t3/userdata/statev2.sqlite`, by the rules the server
  itself uses to recover work after a restart: a run in `orchestration_v2_projection_runs` that is
  `preparing`, `starting`, `running` or `waiting` (on approval or input), a `queued` run that is not
  held (`queueHeld`), or a provider thread with `pendingBackgroundTasks`. Deleted threads do not
  count; an unreadable database, or a missing one on a machine with a T3 server, counts as busy.
  Everything slow happens first: `t3 update` without `--yes` only stages the new version (no
  terminal, so the service keeps running until its next restart), and the customized server is
  built, copied and probed as `*.customize-new`. Then it checks every minute for up to 4 hours
  (`T3CODE_CUSTOMIZE_IDLE_WAIT_MINUTES`), swaps the files in by renaming, runs `daemon-reload` (the
  unit `t3 update` rewrote) and checks once more right before `systemctl restart`. Still busy: it
  stops with `deferred: threads busy` (exit 4, fleet says the same) and restarts nothing; the next run
  tries again. A restart deferred after the swap leaves `~/.t3/runtime/.t3code-customize-restart-pending`,
  and a run that finds the build already installed still restarts (gated) while that marker, or
  T3's own `.restart-pending` for the active version, is there. A failed health check rolls back to stock
  and restarts only while idle; otherwise stock waits on disk for the next restart. Run from a T3
  agent on devbox1, `server` moves itself to a systemd unit, which waits for that agent's turn to
  end, so never wait on that unit in the same turn: end the turn and check
  `journalctl --user -u t3code-customize-server-run` later.
- **How each machine gets a new nightly:**
  - Mac: T3's own updater. In the customized build it downloads a new nightly as soon as it finds
    one and installs it when Tim quits the app (`patches-tt/0007`); nothing restarts the app for
    it. The install changes the app's `Info.plist`, the `autoupdate` LaunchAgent rebuilds the
    overlay, and the next launcher start loads it (opened before that, it opens stock and starts the
    rebuild). On the MacBook Pro (`"ios": true`) the same run then builds the iOS app for the new
    nightly and uploads it to TestFlight. A re-signed copy at `~/Applications/T3 Code (Customized).app`
    from older versions of this tool ran with `T3CODE_DISABLE_AUTO_UPDATE=true`, so it never
    updated; `install_mac_launcher` removes it, and none may remain.
  - devbox1: the `autoupdate` timer at 04:30 runs `server --t3-update`: `t3 update` stages the
    newest `t3@nightly` (a no-op when it already runs it), the customized server is built for it, and
    the one restart waits for idle as above. devbox1 has no `--fix`: its repo is a Syncthing copy
    without `.git` or `gh`, so it cannot publish a port. When the patches break there, it stays on
    its working version and the MacBook Pro's port reaches it through `fleet`.
  - The MacBook Pro (`"fix": "claude"` in `machines.json`) ports broken patches unattended and
    publishes them; see "Unattended ports".
- **Asked to update** ("update", "zijn er updates", "update alles"): follow
  `.agents/playbooks/update.md`.
- **A new machine:** follow "A new machine" in `README.md`. A new Linux box is first set up
  with `~/Devops/Personal/playbook-new-box`; this repo only adds the patches.
- Never edit a machine's T3 install by hand; `server`, `server-off` and `update` own it. On a Mac,
  T3's own updater installs new releases into the untouched app; `update` (and `autoupdate`) only
  rebuild the overlay for it, and until then the launcher opens stock.
- Python must stay compatible with macOS's system Python 3.9.

### Unattended ports

Tim's standing grant (retro of 2026-10-16): when `--fix <agent>` ported the patches without him,
`publish_port` commits the port to the branch `port/nightly-<version>`, pushes it and opens a PR
against `main`. It merges that PR (squash) and starts `fleet`, without asking, only when both hold:

1. every test, typecheck and lint in `checks.json` and `checks-*.json` that the run applies passed
   (the port did not run with `--skip-checks`), and
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
Only a machine with git and `gh` can publish; in `machines.json` that is the MacBook Pro. Anything
else leaves the PR open and notifies Tim; that machine already runs the port. The grant covers
exactly this case. An agent porting by hand follows the normal PR flow.

### Changing a patch yourself

The source checkout is one per machine, shared by every thread and by `fleet`, `update` and
`autoupdate`. Outside a tool run, check the other T3 threads first (`~/.agents/rules/t3-code.md`),
then change patches in your own detached worktree:
`git -C ~/.cache/t3code-customize/t3code worktree add --detach <dir> HEAD`, install as in "Fix",
then run `node_modules/.bin/effect-tsgo patch` (as `checks` does; without it `tsc` skips the Effect
diagnostics, such as `Date.now()` in Effect code, that fail the build elsewhere), run the checks there, and regenerate the patch folder as `export_patches` does
(`git format-patch --no-signature --zero-commit`, one file per commit). Remove the worktree when done.

### Porting own patches

The tool applies the shared patches, rebases them onto the nightly, then applies
`patches-tt/` with `git am --3way` (and `ios` then `patches-ios/`). When an own patch conflicts, a `git am` is stopped in
the source checkout: resolve each file, `git add` it, then `git am --continue`. Keep
upstream's change and carry the intent from the table onto it. The rules in "Fix" above
apply (one commit per patch, no weakened tests). If `ios` stopped, finish with
`./t3code-customize ios --resume`, not `build --resume`: only `ios` applies `patches-ios/`.

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
   unmerged: report it and ask whether to keep the patch. `ported-prs.json` lists these
   PRs with their ported heads; `./t3code-customize status` prints each one's state and
   action. Keep it in step with the rows. For a row that works around an upstream issue,
   check the issue (`gh issue view <n> --repo pingdotgg/t3code`) the same way.
3. Run the checks (`checks.json` plus `checks-tt.json`, and `checks-ios.json` for `ios`; the tool runs them) and the row's
   check.
4. Commit changed `patches-port/`, `patches-tt/` and `patches-ios/` as `chore: port patches to nightly <version>`.
5. Report per row: unaffected, ported (what changed), or needs a decision.

When upstream changes `t3code-customize`, merge it by hand if `pull_latest` could not:
keep the `update`, `autoupdate`, `server`, `fleet`, `ios` and own-patch code, the lock that
names its holder and Python 3.9 compatibility, then run `python3 -m py_compile t3code-customize` and `./t3code-customize status`.

### Fork changes and their checks

| Change | Files | Intent | Check |
| --- | --- | --- | --- |
| Claude context window (`patches-tt/0001`) | `apps/server/src/orchestration-v2/Adapters/ClaudeAdapterV2.ts`, `apps/server/src/provider/Drivers/ClaudeSkills.ts`, `apps/web/src/components/chat/ComposerStats.logic.ts` | Claude context is measured against the smaller of the model window and `autoCompactWindow` (T3's "Auto-compact after", else Claude's user, project and local settings files, read once per session, as the CLI does). Label "Managed by Claude". | Tests in `checks-tt.json`. In the app, with `"autoCompactWindow": 300000` in `~/.claude/settings.json`, the context popover shows a window of 300,000. |
| Worktree handoff continuation (`patches-tt/0002`) | `apps/server/src/mcp/WorktreeMcpService.ts`, `apps/server/src/orchestration-v2/{Orchestrator,RunExecutionService,ProviderSessionManager,EffectOutbox,EffectWorker}.ts`, `packages/contracts/src/orchestrationV2.ts`, `packages/provider-core/src/server/ProviderAdapter.ts` | Port of upstream PR pingdotgg/t3code#15203 (fixes #15136): after `t3_worktree_handoff` the continuation prompt starts instead of "Provider event stream closed unexpectedly". Ported head `19f7ff972e13`, which also ends the run's open root items (the handoff call itself) as interrupted on a planned detach, so they do not stay running. Drop this patch once `gh pr view 15203 --repo pingdotgg/t3code --json state` says MERGED and that nightly is installed everywhere. Agents do not use the handoff for implementation (`~/.agents/rules/t3-code.md` delegates to a worker); the patch only keeps a manual handoff working. | Tests in `checks-tt.json`. In T3, a thread on the project root calls `t3_worktree_handoff` with a `continuationPrompt` and continues in the worktree; the handoff call shows as ended, not running. |
| Child threads (`patches-tt/0003`) | `packages/contracts/src/orchestrationV2.ts`, `apps/server/src/orchestration-v2/{Orchestrator,ProjectionStore,ThreadLaunchService,ThreadManagementService,ThreadSettlementService}.ts`, `apps/server/src/mcp/{OrchestratorMcpService.ts,toolkits/project/handlers.ts}`, `packages/client-runtime/src/state/{models,threadCommands,threadShell.test}.ts`, `apps/web/src/components/{Sidebar.tsx,Sidebar.families.ts,threadActionMenu.logic.ts}`, `apps/web/src/contextMenuFallback.ts` | Server side of upstream PR pingdotgg/t3code#16699: `t3_thread_launch` and `create_threads` record `openedByThreadId`. The sidebar nests a child under its opener as in Claude.app (guide line, no favicon) when both sit in the same section; a nested child shows its status (working, input, approval, failed, done) as a colored icon where the time would be. The server records `settledBy` (`agent` for T3 tools, `auto` for automatic settlement; absent for a user settle). A settled child stays under an opener that is not settled, folded behind a dimmed "N settled" row of its own (open per session, not stored); one that works or waits on input or approval again shows as a live child. Settling the opener moves the whole family to Settled; a live child under a settled opener stays in its own section. Settling a thread also settles its idle children (`settledBy: auto`, and so on down the family); a child that still works, waits on input or approval, or that the user pinned, snoozed or kept from auto-settling stays unsettled. A `delegate_task` worker (not a provider-native subagent) nests under the thread that delegated it, always in that thread's section, and stays hidden while it is not shown; upstream already routes the worker's questions to it. Workers are placed before settled children, so a settled thread a worker opened folds under the worker's family wherever the worker renders. Every opener with children has a disclosure row right under it: a chevron, the count and what the children do ("6 child threads · 1 failed · 1 new · 2 working · 2 settled"). Clicking it, or the context menu "Hide/Show child threads", folds the family; collapsed, only children needing input or approval and the open thread stay. Families start expanded, except in Settled, where every entry starts collapsed (a new settle, or a snooze that wakes back into Settled, also when another device woke it) and an expand holds until the family leaves Settled. The thread shell carries `lastSnoozeWakeAt` for this (a wake by hand stamps it; a wake by time keeps `snoozedAt`). Folds persist in localStorage: `t3code:sidebar:collapsed-child-threads` (live head keys) and `t3code:sidebar:expanded-settled-child-threads` (`<headKey>@<settledAt>|<snoozedAt>|<lastSnoozeWakeAt>`); an expansion is dropped once its head is outside Settled, and any fold once its thread is gone from a loaded environment. Settled pages a family at a time, so a child never shows without its head; "Show N more" and "N settled hidden" count threads. The disclosure buttons name the action, count and opener for screen readers ("Show 6 child threads of <title>, 1 failed"). Older threads stay flat. If upstream ships its own child-thread sidebar (#16699 web side or #15988), propose dropping this patch. | Tests in `checks-tt.json`. In T3, a thread that calls `t3_thread_launch` shows the new thread nested under it while both are in the same section; a `delegate_task` worker shows nested under its orchestrator. The disclosure row under the opener folds the family. Settling a child keeps it under its opener behind "1 settled"; settling the opener moves the family to Settled, collapsed. |
| Direct APNs push (`patches-tt/0004`) | `apps/server/src/directPush/{DirectPush,ApnsTransport,agentActivityDelivery}.ts`, `apps/server/src/relay/AgentAwarenessRelay.ts`, `apps/server/src/{ws,server}.ts`, `apps/server/src/environment/ServerEnvironment.ts`, `apps/server/src/auth/RpcAuthorization.ts`, `apps/server/src/observability/RpcInstrumentation.ts`, `packages/contracts/src/rpc.ts` | With secret `direct-push-apns` (`~/.t3/userdata/secrets/direct-push-apns.bin`, from 1Password "T3 Code TT APNs key", field `serverconfig`) the server sends its own threads' notifications and Live Activity updates to APNs itself (logic ported from `infra/relay/src/agentActivity/`), because T3's relay key cannot push to `nl.timvdhoorn.t3code`. RPCs `server.registerPushDevice`, `server.registerPushLiveActivity`, `server.getPushActivitySnapshot`. Without the key it behaves as upstream. With work on two servers at once, the last one to push owns the shared Live Activity card. To keep orchestration quiet, a Done goes out only after the thread stayed finished for 60 s (`COMPLETION_SETTLE_MS`; a wake from a background task or worker cancels it), and a thread an agent opened (`openedByThreadId`) never sends Done, only input, approval and failure. Workers and provider subagents send nothing, as upstream. | Tests in `checks-tt.json`. With the key installed, an agent on devbox1 that finishes or needs input buzzes the iPhone and updates the Live Activity. |
| Customized build label (`patches-tt/0005`) | `apps/web/{vite.config.ts,src/vite-env.d.ts,src/branding.ts,src/branding.logic.ts}`, `apps/web/src/components/{settings/SettingsPanels.tsx,sidebar/SidebarChrome.tsx}`, `apps/desktop/{vite.config.ts,src/app/DesktopAppIdentity.ts}` | `t3code-customize` passes `T3CODE_CUSTOMIZED_BUILD` ("<recipe> <build time>", `customized_build_stamp`) to the web, server and desktop builds. The sidebar shows the first 7 characters of the recipe next to the logo (tooltip: full recipe and build time), Settings > General > About shows a "Customized build" row, and the macOS About panel reads "<commit>, custom <recipe>". Stock builds show none of it. The recipe matches `t3code-customize status` and `identity`. | `apps/web/src/branding.customized.test.ts`, `apps/desktop/src/app/DesktopAppIdentity.customized.test.ts`. In the app, the label sits next to the logo. |
| Idle compaction (`patches-tt/0006`) | `apps/server/src/orchestration-v2/{IdleCompaction,IdleCompactionService,Orchestrator,ProjectionStore,RunExecutionService,CommandPolicy,ThreadManagementService}.ts`, `apps/server/src/relay/AgentAwarenessRelay.ts`, `apps/server/src/{config,server}.ts`, `packages/contracts/src/{orchestrationV2,settings}.ts`, `packages/shared/src/orchestrationV2{ThreadError,PendingBackgroundWork,Timeline}.ts`, `packages/client-runtime/src/{handoff,operations/commands,state/threadExecution,state/threadWorkflows}.ts`, `apps/web/src/components/{ChatView.tsx,settings/SettingsPanels.tsx}` | Port of upstream PR pingdotgg/t3code#19662: with Settings > "Compact idle threads" (opt-in, default off) an idle root thread compacts once in the last 10% of its provider's prompt cache TTL (Claude 60 min, others 30 min; `T3CODE_IDLE_COMPACTION_DELAY_MS` overrides the delay), and the run stays out of chat state, settlement, pushes, sends, forks and limits. Ported head `84698a79b865`. Fork deviation: the context floor `MIN_IDLE_COMPACTION_CONTEXT_TOKENS` is 100,000 tokens (Claude Code's own idle-compaction floor) instead of the PR's 20,000. The relay's idle-run filter also gates direct APNs push (`patches-tt/0004`), so an idle compaction never sends a notification or Live Activity update; a child thread compacting while idle still settles with its opener (`patches-tt/0003`). Drop this patch once `gh pr view 19662 --repo pingdotgg/t3code --json state` says MERGED and that nightly is installed everywhere; if upstream merged its own threshold, propose to Tim to accept it or keep a threshold-only patch. Head moved: port the new commits. CLOSED unmerged: ask Tim. | Tests in `checks-tt.json` (`IdleCompactionService.test.ts` holds the 99,999 / 100,000 boundary, `AgentAwarenessRelay.test.ts` the direct-push silence, `ProjectionSettlement.test.ts` the child settle). In T3, with the setting on and a small `T3CODE_IDLE_COMPACTION_DELAY_MS`, a thread above 100k tokens shows one compaction row after the delay and a thread below it none. |
| Updates on quit (`patches-tt/0007`) | `apps/desktop/src/updates/{DesktopUpdateAutomation,DesktopUpdates,updatesTestHarness}.ts` | In a build stamped with `T3CODE_CUSTOMIZED_BUILD` (`patches-tt/0005`) T3's updater downloads a new release as soon as a check finds it (through its own download action, so Settings shows the progress) and sets electron-updater's `autoInstallOnAppQuit`, so Squirrel installs it when Tim quits the app. It never calls `quitAndInstall` or restarts the app on its own; "Restart to update" stays a click. Stock builds keep upstream's manual download and install. It does not fight the overlay: the install changes `Info.plist`, which the `autoupdate` LaunchAgent watches to rebuild (see "Machines"). If upstream starts downloading automatically itself, propose dropping this patch. | `apps/desktop/src/updates/DesktopUpdateAutomation.test.ts` (customized: download after a check, install on quit, no restart; stock: neither). In the app, a new nightly shows as downloaded without a click and is installed after quitting. |
| Agent or subagent label (`patches-tt/0008`) | `packages/client-runtime/src/state/{subagentDisplay,threadExecution,threadShell}.ts`, `packages/shared/src/orchestrationV2PendingBackgroundWork.ts`, `packages/contracts/src/orchestrationV2.ts`, `apps/web/src/components/ChatView.tsx`, `apps/web/src/components/chat/{ThreadRelationshipsControl.logic.ts,ThreadRelationshipsControl,SubagentTooltipContent,V2LifecycleRow,MessagesTimeline}.tsx` | A child agent says what it is, from the subagent's `origin`, always lowercase: `app_owned` (a T3 `delegate_task` worker with its own provider session and thread) reads "agent", `provider_native` (a provider's own subagent, such as Claude's Agent tool, inside the parent's process) reads "subagent". The Lineage rows show it as a muted label after the title, their hover card after the status ("Running · agent"), and the timeline card prefixes its status ("agent · Running"; next to the title when the card shows a result). The pending subagent task carries the turn item's `origin`, so the background-work pill (web and mobile) reads "Waiting on agent <title>" for a worker, "Waiting on subagent <title>" for a provider-native one, and counts them apart ("Waiting on 2 agents and 1 subagent"). Every upstream string that names the child kind follows, lowercase, with an unknown origin read as "subagent": an untitled card's title ("agent" / "subagent", `subagentFallbackTitle`), the Lineage relation ("agent" / "subagent", from the projected subagent or else the child thread's `creationSource`; the other side "parent agent"), the divider at the top of a child thread ("agent of" / "subagent of"), the child input banner ("agent needs approval", "2 agents need input", "1 agent and 1 subagent need you", by `delegatedByThreadId`), the group rows ("Ran 2 agents", "Kicked off 1 agent and 2 subagents", `childAgentCountLabel`), the Lineage stop control (tooltip "Stop agent", label "Stop agent <title>", toast "Could not stop agent") and the pill's link label ("Open agent <title>", from the item's `noun`). No kind label when the origin is unknown (the pill keeps "subagent"). Upstream tests that named the old strings (`MessagesTimeline.browser.test.tsx`, `ThreadRelationshipsControl.agents.browser.test.tsx`, `threadExecution.test.ts`) expect the new ones and are in `checks-tt.json`. Stock styling only. If upstream labels the two kinds itself, propose dropping this patch. | Tests in `checks-tt.json` (`threadExecution.kind.test.ts` holds the pill, `subagentDisplay.kind.test.ts` the titles and counts, `threadShell.kind.test.ts` the input banner, `ThreadRelationshipsControl.kind.browser.test.tsx` the relation and the stop control). In T3, a thread with a `delegate_task` worker and a Claude Agent-tool subagent shows "agent" and "subagent" on their timeline cards and Lineage rows, and a parent waiting on a worker shows "Waiting on agent <title>". |
| iOS identity (`patches-ios/0001`) | `apps/mobile/app.config.ts` | `T3CODE_IOS_BUNDLE_ID`, `T3CODE_IOS_TEAM_ID` and `T3CODE_IOS_APP_NAME` sign a full-capability build (widgets, share extension, app group, push entitlement) under your own team; OTA updates, Clerk associated domains and native Sign in with Apple are off for it (they are bound to T3's team). Upstream's `T3CODE_IOS_PERSONAL_TEAM` path stays as it was. | Tests in `checks-ios.json`. `./t3code-customize ios` archives and uploads; the app installs from TestFlight and pairs with devbox1. |
| iOS system font (`patches-ios/0002`) | `apps/mobile/{global.css,app.config.ts}`, `apps/mobile/src/lib/{useFontFamily.ts,uniwind-platform-variants.fixture.cjs}`, `apps/mobile/src/native/EnrichedMarkdownText.tsx`, `apps/mobile/modules/t3-composer-editor/ios/T3ComposerEditorView.swift` | UI text on iOS is the system font (SF Pro): the sans families are `System` on iOS, the weight utilities add `font-weight`, markdown bold sets its weight, the composer chips use the system font, DM Sans is no longer bundled for iOS. Android and monospace are unchanged. | `apps/mobile/src/lib/system-font.test.ts` compiles the real `global.css` per platform. In the app, text renders in SF Pro with medium and bold weights intact. |
| iOS stats for nerds (`patches-ios/0003`) | `packages/client-runtime/src/state/{composerStats,contextWindow}.ts` (moved from `apps/web`, web keeps re-exports), `apps/web/src/components/{ChatView.tsx,chat/ComposerStats.tsx}`, `apps/mobile/src/features/threads/{ComposerStats.tsx,composerStatsRow.ts,ThreadComposer.tsx,ThreadDetailScreen.tsx}`, `apps/mobile/src/state/{use-composer-stats,use-thread-composer-state}.ts`, `apps/mobile/src/persistence/mobile-preferences.ts`, `apps/mobile/src/features/settings/SettingsThreadsRouteScreen.tsx` | The composer shows the desktop's stats line on one line, without the output rate: 5h, week, context and the cache hit rate ("96% cached", whole percents, truncated). Both forms of the row are measured off screen: the full row shows while it fits, else shorter meters and "ctx" (both limits at 100% on an iPhone 17 Pro, a narrow screen), and at text sizes where even that does not fit it wraps instead of clipping. The cache chip opens the turn sheet, which keeps tok/s; a turn without a cache figure gets a plain "tokens" chip in its place, so the sheet stays reachable (the context chip always opens the context sheet). The sheets carry the desktop's detail rows and a Compact now action, behind Settings > Threads > Stats for nerds (off by default, per device). Web and mobile share the calculations. | Tests in `checks-ios.json`. `apps/mobile/src/features/threads/composerStatsRow.test.ts` holds the row (no tok/s, cache kept, compact form, the layout choice, the tokens chip). In the app, with the switch on, a thread shows the stats on one line under the composer at the default text size, and its sheets match the desktop popovers. |
| iOS child threads (`patches-ios/0004`) | `packages/client-runtime/src/state/{threadFamilies,threadShell}.ts` (web `Sidebar.families.ts` re-exports), `apps/mobile/src/features/threads/{threadListV2.ts,thread-list-v2-items.tsx,ThreadNavigationSidebar.tsx,use-thread-list-v2-shelf-preferences.ts}`, `apps/mobile/src/features/home/{HomeRouteScreen,HomeScreen,thread-swipe-actions}.tsx`, `apps/mobile/src/state/entities.ts`, `apps/mobile/src/persistence/mobile-preferences.ts` | The thread list and iPad sidebar nest child threads under their opener with the desktop's rules (`openedByThreadId`, settled children folded behind an "N settled" row under an opener that is not settled, the family to Settled with its opener, `delegate_task` workers in their delegator's section), guide line, no favicon, the disclosure row under each opener with the same summary, defaults, pruning, family paging and VoiceOver labels (folds in preferences `threadListCollapsedChildThreadKeys` and `threadListExpandedSettledChildThreadKeys`, the "N settled" row per session), and "Hide/Show child threads" in the long-press menu. The guide line's last corner lands on the title's midline and sits left of the swipeable, which starts right of the corner, so the guide stays put and a swiped row's title slides under the row's own edge instead of across the line; nested rows get compact icon-only swipe actions that fit their height. Older threads stay flat. Depends on `patches-tt/0003`. | Tests in `checks-ios.json`. In the app, a thread that launched another shows it nested beneath it with the disclosure row; a swiped child row keeps its height and guide line, and its title clips at the row's edge right of the guide. |
| iOS direct push (`patches-ios/0005`) | `apps/mobile/app.config.ts`, `apps/mobile/src/connection/{direct-push,runtime}.ts`, `apps/mobile/src/features/agent-awareness/{capabilities,remoteRegistration,directPushSnapshot}.ts`, `apps/mobile/src/features/settings/{SettingsNotificationsRouteScreen,SettingsRouteScreen,DirectPushSettingsNotificationsRouteScreen}.tsx` | A custom-identity build (`extra.directServerPush`) registers its push token, Live Activity token and preferences with every paired server, again whenever a server connects, with no Clerk or relay involved. Settings > Notifications shows a screen with two stock switches. The official build keeps the relay path. Depends on `patches-tt/0004`. | Tests in `checks-ios.json`. In the app, Settings > Notifications shows both switches on once a server with the key has accepted the device. |
| iOS Claude theme (`patches-ios/0006`) | `packages/shared/src/themePalettes.ts`, `apps/mobile/src/lib/{mobileTheme,mobileThemeRuntime}.ts`, `apps/mobile/scripts/generate-uniwind-themes.mts`, `apps/mobile/{generated-uniwind-themes.css,generated-uniwind-theme-names.json,uniwind-types.d.ts}` | The desktops' `claude` environment theme (`~/.t3/userdata/themes/claude.json`) as a mobile palette in Settings > Appearance, light and dark; roles the file omits fall back to T3 Chat as on desktop; `messageAction` is `#ba5b3b` so white button text keeps 4.5:1. Not a web built-in, so desktops can still publish `claude.json`. If `claude.json` changes, update `CLAUDE_THEME`; if upstream mobile starts following environment themes, propose dropping this patch. | Tests in `checks-ios.json`. In the app, Appearance shows a Claude card; selecting it gives a `#151515` canvas in dark and `#fcfcfb` in light with terracotta primary buttons. |
| iOS agent or subagent label (`patches-ios/0007`) | `apps/mobile/src/features/threads/{threadAgentsPresentation.ts,SubagentRow.tsx,thread-subagent-group.tsx,thread-work-log.tsx}`, `apps/mobile/src/lib/threadActivity.ts` | The mobile child-agent rows (the inline subagent card and its expanded group in the thread timeline, and the Agents sheet) read "agent · Working" for a `delegate_task` worker and "subagent · Working" for a provider-native one, lowercase, with the shared `subagentKindLabel` from `patches-tt/0008` (which also gives the mobile background-work pill "Waiting on agent <title>"). The kind is in the secondary text color, the status keeps its tone color, and VoiceOver reads the kind with the row. An untitled row or timeline item is titled by its kind ("agent" / "subagent"), the grouped card counts by kind ("2 agents", "1 agent and 2 subagents"), and so does the spawn card's VoiceOver hint ("Double tap to show 1 agent and 2 subagents", `agentSpawnCardHint`), and the input banner in a thread uses the shared title from `patches-tt/0008` ("agent needs approval"). No kind label when the origin is unknown. Depends on `patches-tt/0008`. | Tests in `checks-ios.json`. In the app, a thread with a `delegate_task` worker and a Claude Agent-tool subagent shows "agent" and "subagent" before their status in the timeline card and the Agents sheet. |
| iOS build | `t3code-customize` (`cmd_ios`, `build_ios`, `ios_app_id`, `ios_testers`), `ios.json` | Builds `apps/mobile` for the nightly commit installed on the Mac with `expo prebuild` and `xcodebuild archive` (automatic signing with the App Store Connect API key), uploads with asc-cli and keeps the internal TestFlight group and its testers. Depends on upstream's `apps/mobile/app.config.ts` version field and Expo prebuild layout. | `./t3code-customize ios` ends with the build on TestFlight; `asccli builds list --app-id <id>` shows it. |
| macOS launcher | `t3code-customize` (`install_mac_launcher`, `cmd_update`, `cmd_autoupdate`) | Upstream's overlay: the signed `T3 Code (Nightly).app` stays untouched (passkeys, keychain, T3's updater work); the launcher in `/Applications/T3 Code (Customized).app` (fork: upstream uses `~/Applications`, which stays the fallback when `/Applications` is not writable) starts it with `--inspect-brk` and loads the build from `~/.local/share/t3code-customize/builds/<build>/overlay`. The fork adds: the launcher removes the re-signed app copy and the launcher earlier versions put in `~/Applications`. `autoupdate on` is a LaunchAgent that watches the app's `Info.plist` and `app.asar` (`WatchPaths`) plus an hourly check; it runs `update --background`, which waits until T3's updater stops writing (`app_settled`), rebuilds and notifies "quit and reopen". A launcher opened on an outdated build opens stock and starts that rebuild (`start_background_update`). When the patches conflict, the notification says to ask an agent in this repo to port them (with `--fix claude` the agent ports unattended and `publish_port` opens, and under the standing grant merges, its PR; see "Unattended ports"). With `--ios` (`autoupdate on --ios`) the run then builds the iOS app when the nightly changed (`update_ios`). | `./t3code-customize status` says the next launch opens the customized build; opening the launcher logs "Opened T3 Code with the customization" in `~/.cache/t3code-customize/logs/launch.log`, and the app shows the stats and child threads. |
| T3 server | `t3code-customize` (`cmd_server`, `build_server`, `install_server_build`, `restart_server`, `server_autoupdate`) | Patched `t3` and `client/` in `~/.t3/runtime/versions/<active>/`, built from tag `v<version>` with `VP_NODE_VERSION` = upstream's `SEA_NODE_VERSION`; originals kept as `*.stock`; health check on port 3773 or back to stock. With `--t3-update` it first stages the newest nightly (`t3 update`, no `--yes`, no terminal); the build is copied and probed as `*.customize-new` (`stage_server_build`), and only the renames and the one restart wait until no thread works (`wait_until_idle`, then `restart_service` checks once more). A rollback restarts only while idle. Depends on upstream's `apps/server/scripts/cli.ts build-exe` and the runtime layout. | `./t3code-customize status` on devbox1 shows "Customized: yes"; `curl` on port 3773 gives 200; `t3 connect status --json` is still linked. |
| Fleet | `t3code-customize` (`cmd_fleet`, `sync_repo`, `fleet_command`, `autoupdate_command`), `machines.json` | One command updates every machine from any machine; files arrive by Syncthing or SSH copy, identical script and recipe hash required before building. Each machine's run waits up to 30 min for a run holding its checkout (`fleet --wait-lock`, printing the holder; a merged port starts it with 180), a server first stages the newest T3 (`--t3-update`), and afterwards fleet runs `autoupdate on` there with the machine's `fix` and `ios` from `machines.json` (the MacBook Pro `--fix claude --ios`, the others neither). | `./t3code-customize fleet` ends with every machine `ok`. `tests/test_unattended_updates.py`. |
| Unattended updates | `t3code-customize` (`busy_threads`, `wait_until_idle`, `restart_service`, `stage_t3_update`, `acquire_lock`, `publish_port`, `code_unchanged`, `update_ios`), `machines.json`, `.gitignore` | New nightlies reach every machine and TestFlight without Tim and never interrupt a running thread: the idle gate and the per-machine route in "Machines", the standing grant in "Unattended ports". Depends on upstream's `statev2.sqlite` projection (`orchestration_v2_projection_runs.status` and `payload_json.queueHeld`, `orchestration_v2_projection_provider_threads.payload_json.pendingBackgroundTasks`, `orchestration_v2_projection_threads.deleted_at`; compare `ProjectionStore`'s runtime recovery query on each nightly) and on `t3 update` staging without restarting when it has no terminal (`apps/server/src/cli/update.ts`). The iOS attempt (`ios-attempt.json`) is recorded once the iOS build worked, so a failed build tries again next hour and a failed upload does not. | `tests/test_unattended_updates.py` (idle gate on a real SQLite file incl. held queues and background tasks, deferral, the last check before a restart, the gated rollback, lock wait, merge decision incl. reordered, `#`, `++`, binary and mode lines, staged files, branch reuse, fleet commands). On devbox1, `sqlite3 -readonly ~/.t3/userdata/statev2.sqlite "select status,count(*) from orchestration_v2_projection_runs group by 1"` lists `running` while an agent works. |
| Hermetic checks | `t3code-customize` (`checks`) | Tests and typechecks run with `HOME` set to an empty temp dir, as in upstream's CI, and `TMPDIR` under `~/.cache/t3code-customize/tmp` (devbox1's `/tmp` is a tmpfs with a user quota that filled up mid-test, `EDQUOT`). Upstream's ClaudeAdapterV2 steer test "(never answers)" reads the real `~/.claude/skills` mid-steer and hangs once there are many skills (devbox1, 73). Upstream's `vp lint` also runs on every file the patches add or change: its `no-hermes-unsupported-apis` rule catches APIs Hermes lacks (`Array#toSorted` crashed the iOS composer stats), which tests on Node and typechecks miss. Before the typechecks `checks` runs `effect-tsgo patch`, as upstream's `prepare` and CI do: `--ignore-scripts` skips it, so a checkout once installed with scripts checked `globalDateInEffect` (`Date.now()` in Effect code) and fresh worktrees did not, and a patch that passed in a worktree failed on the MacBook Pro. A `*.browser.test.*` file in a check list runs in its app's `browser` project (`vp test run --project browser` from `apps/web`; from the root it lands in the node pool and fails), with Playwright's headless Chromium installed into `~/.cache/t3code-customize/ms-playwright` (`install_playwright_browser`; the empty `HOME` hides the user's cache, and an install prunes browsers from its folder that no installed Playwright uses). On a Linux release Playwright does not know yet (devbox1, Ubuntu 26.04) it retries with the `ubuntu24.04` build. | `./t3code-customize build --resume` passes the checks on devbox1. |
| Checkout guard | `t3code-customize` (`prepare`, `main`) | A fresh build stops instead of aborting a stopped rebase or `git am` or discarding uncommitted edits in the source checkout, since they may be a port in progress; the lock file `~/.cache/t3code-customize/lock` names the run that holds it, and a second run says so. A build undoes its own rewrites of tracked files when its build step ends, also on failure (`build_rewrites_discarded`: prepare left the checkout clean, so whatever is modified then came from the build, such as TanStack Router's `routeTree.gen.ts` or Expo prebuild's `apps/mobile/uniwind-types.d.ts`). For a run killed before that, `GENERATED` lists those files and `prepare` restores them first when nothing else changed, so a finished build never blocks the next one. That also drops a hand edit to only those files: they are generated, so change their generator or a patch commit instead; next to any other change they stay and the guard stops. | With a tracked edit in the checkout, `prepare` stops and the edit survives; with the lock held, a second run prints the holder. `tests/test_checkout_guard.py`. |
| Typecheck with tsc-rs | `t3code-customize` (`typechecker`, `checks`), `tests/test_typechecker.py` | `checks` typechecks with `tsc-rs --noEmit`, as upstream's `typecheck` scripts do since 2026-10-11 (808bee7daa; `tsc-rs` 0.7.0, a port of the TS 7 compiler with the Effect diagnostics of `@effect/tsgo` 0.51.1 built in). Without `node_modules/.bin/tsc-rs` (an older nightly) it uses `tsc` and says so in the log. `effect-tsgo patch` still runs first, for that fallback. Measured on devbox1 (nightly `8fabde12`, idle, sequential, the 13 packages in `checks*.json`): 81 s and 8.3 GB peak with `tsc`, 26 s and 4.3 GB with `tsc-rs`; `apps/server` alone 34 s / 8.3 GB against 9 s / 4.3 GB, the step that took over 35 min on the swapping 16 GB MacBook Pro. `/usr/bin/time` reports about 49 MB for `tsc-rs`, which is wrong: sum the RSS of its process session instead. Both fail with the same diagnostic on `Date.now()` in `Effect.gen` (TS377067 `globalDateInEffect`) and on a plain type error (TS2322); `tsc` exits 1, `tsc-rs` 2. If upstream drops `tsc-rs`, go back to `tsc`. | `tests/test_typechecker.py`. In a checkout, a file with `Date.now()` in `Effect.gen` fails `node_modules/.bin/tsc-rs --noEmit -p packages/shared/tsconfig.json` with TS377067. |
| Ported-PR check | `t3code-customize` (`report_ported_prs`, `main`), `ported-prs.json` | `status`, and `build`, `update` and `server` when they end (also after a conflict), print each PR in `ported-prs.json` with its upstream state and action: open with the ported head (keep), head moved (port the new commits), merged (drop once the nightly has it; "in your nightly" when its merge commit is in the installed nightly), closed (ask Tim). Without `gh` or offline it prints one skip line and carries on. | `./t3code-customize status` ends with one line per ported PR. |
| Upstream merge | `t3code-customize` (`pull_latest`) | Each run merges `upstream/main` when it merges cleanly, else continues with the patches it has. | `git log upstream/main..HEAD` shows only fork commits after a run. |

## Agent skills

### Issue tracker

GitHub Issues on the fork `timvdhoorn/t3code-customize-tt`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created when needed. See `docs/agents/domain.md`.
