# Porting the patches to a new T3 Code nightly

These instructions are for a coding agent. A person can follow them too.

The patches in `patches/` are commits made against the upstream commit in
`patches/base.txt`. Upstream moves fast, so they often stop applying cleanly. Your job
is to carry them onto the user's nightly with every feature still working.

## Start

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

### Ownership

| Upstream owns (never commit changes) | The fork owns (commit changes) |
| --- | --- |
| `patches/*.patch`, `patches/base.txt`, `checks.json` | `patches-port/`, `patches-tt/`, `checks-tt.json`, `patches-ios/`, `checks-ios.json`, `ios.json`, this section, `CLAUDE.md` |
| the Linux, Windows and macOS build and launch paths in `t3code-customize`, `platform_support.py`, `macos/`, `install.ps1`, `tests/`, `docs/macos.md` | update, autoupdate, server, fleet and ios code in `t3code-customize`, `machines.json`, the `README.md` macOS, server and machines sections |

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
  pushed, run `./t3code-customize fleet` and report the summary per machine. It restarts
  devbox1's T3 server, which reconnects open sessions; say so when you report.
- **A new machine:** follow "A new machine" in `README.md`. A new Linux box is first set up
  with `~/Devops/Personal/playbook-new-box`; this repo only adds the patches.
- Never edit a machine's T3 install by hand; `server`, `server-off` and `update` own it. On a Mac,
  T3's own updater installs new releases into the untouched app; `update` (and `autoupdate`) only
  rebuild the overlay for it, and until then the launcher opens stock.
- Python must stay compatible with macOS's system Python 3.9.

### Changing a patch yourself

The source checkout is one per machine, shared by every thread and by `fleet`, `update` and
`autoupdate`. Outside a tool run, check the other T3 threads first (`~/.agents/rules/t3-code.md`),
then change patches in your own detached worktree:
`git -C ~/.cache/t3code-customize/t3code worktree add --detach <dir> HEAD`, install as in "Fix",
run the checks there, and regenerate the patch folder as `export_patches` does
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
   unmerged: report it and ask whether to keep the patch.
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
| Child threads (`patches-tt/0003`) | `packages/contracts/src/orchestrationV2.ts`, `apps/server/src/orchestration-v2/{Orchestrator,ProjectionStore,ThreadLaunchService,ThreadManagementService}.ts`, `apps/server/src/mcp/{OrchestratorMcpService.ts,toolkits/project/handlers.ts}`, `packages/client-runtime/src/state/{models,threadCommands,threadShell.test}.ts`, `apps/web/src/components/{Sidebar.tsx,Sidebar.families.ts,threadActionMenu.logic.ts}`, `apps/web/src/contextMenuFallback.ts` | Server side of upstream PR pingdotgg/t3code#16699: `t3_thread_launch` and `create_threads` record `openedByThreadId`. The sidebar nests a child under its opener as in Claude.app (guide line, no favicon) when both sit in the same section; a nested child shows its status (working, input, approval, failed, done) as a colored icon where the time would be. The server records `settledBy` (`agent` for T3 tools, `auto` for automatic settlement; absent for a user settle). A settled child goes to Settled whoever settled it, so finished work leaves its opener's family; only a settled child that still works or waits on input or approval stays under an opener that is still pinned, active or working; a live child under a settled opener stays in its own section. A `delegate_task` worker (not a provider-native subagent) nests under the thread that delegated it, always in that thread's section, and stays hidden while it is not shown; upstream already routes the worker's questions to it. Context menu "Hide/Show child threads"; collapsed, only children needing input or approval and the open thread stay, the rest become a stub "N child threads · x failed · y new · z working". Older threads stay flat. If upstream ships its own child-thread sidebar (#16699 web side or #15988), propose dropping this patch. | Tests in `checks-tt.json`. In T3, a thread that calls `t3_thread_launch` shows the new thread nested under it while both are in the same section; a `delegate_task` worker shows nested under its orchestrator. |
| Direct APNs push (`patches-tt/0004`) | `apps/server/src/directPush/{DirectPush,ApnsTransport,agentActivityDelivery}.ts`, `apps/server/src/relay/AgentAwarenessRelay.ts`, `apps/server/src/{ws,server}.ts`, `apps/server/src/environment/ServerEnvironment.ts`, `apps/server/src/auth/RpcAuthorization.ts`, `apps/server/src/observability/RpcInstrumentation.ts`, `packages/contracts/src/rpc.ts` | With secret `direct-push-apns` (`~/.t3/userdata/secrets/direct-push-apns.bin`, from 1Password "T3 Code TT APNs key", field `serverconfig`) the server sends its own threads' notifications and Live Activity updates to APNs itself (logic ported from `infra/relay/src/agentActivity/`), because T3's relay key cannot push to `nl.timvdhoorn.t3code`. RPCs `server.registerPushDevice`, `server.registerPushLiveActivity`, `server.getPushActivitySnapshot`. Without the key it behaves as upstream. With work on two servers at once, the last one to push owns the shared Live Activity card. To keep orchestration quiet, a Done goes out only after the thread stayed finished for 60 s (`COMPLETION_SETTLE_MS`; a wake from a background task or worker cancels it), and a thread an agent opened (`openedByThreadId`) never sends Done, only input, approval and failure. Workers and provider subagents send nothing, as upstream. | Tests in `checks-tt.json`. With the key installed, an agent on devbox1 that finishes or needs input buzzes the iPhone and updates the Live Activity. |
| Customized build in About (`patches-tt/0005`) | `apps/web/{vite.config.ts,src/vite-env.d.ts,src/branding.ts,src/branding.logic.ts}`, `apps/web/src/components/settings/SettingsPanels.tsx` | Settings > About shows a "Customized build" row with the recipe hash and build time that `t3code-customize` passes as `T3CODE_CUSTOMIZED_BUILD` (`build_web_and_server`); stock builds show nothing. The recipe matches `t3code-customize status` and `identity`. | `apps/web/src/branding.customized.test.ts`. In the app, Settings > About shows the row under Version. |
| iOS identity (`patches-ios/0001`) | `apps/mobile/app.config.ts` | `T3CODE_IOS_BUNDLE_ID`, `T3CODE_IOS_TEAM_ID` and `T3CODE_IOS_APP_NAME` sign a full-capability build (widgets, share extension, app group, push entitlement) under your own team; OTA updates, Clerk associated domains and native Sign in with Apple are off for it (they are bound to T3's team). Upstream's `T3CODE_IOS_PERSONAL_TEAM` path stays as it was. | Tests in `checks-ios.json`. `./t3code-customize ios` archives and uploads; the app installs from TestFlight and pairs with devbox1. |
| iOS system font (`patches-ios/0002`) | `apps/mobile/{global.css,app.config.ts}`, `apps/mobile/src/lib/{useFontFamily.ts,uniwind-platform-variants.fixture.cjs}`, `apps/mobile/src/native/EnrichedMarkdownText.tsx`, `apps/mobile/modules/t3-composer-editor/ios/T3ComposerEditorView.swift` | UI text on iOS is the system font (SF Pro): the sans families are `System` on iOS, the weight utilities add `font-weight`, markdown bold sets its weight, the composer chips use the system font, DM Sans is no longer bundled for iOS. Android and monospace are unchanged. | `apps/mobile/src/lib/system-font.test.ts` compiles the real `global.css` per platform. In the app, text renders in SF Pro with medium and bold weights intact. |
| iOS stats for nerds (`patches-ios/0003`) | `packages/client-runtime/src/state/{composerStats,contextWindow}.ts` (moved from `apps/web`, web keeps re-exports), `apps/web/src/components/{ChatView.tsx,chat/ComposerStats.tsx}`, `apps/mobile/src/features/threads/{ComposerStats.tsx,ThreadComposer.tsx,ThreadDetailScreen.tsx}`, `apps/mobile/src/state/{use-composer-stats,use-thread-composer-state}.ts`, `apps/mobile/src/persistence/mobile-preferences.ts`, `apps/mobile/src/features/settings/SettingsThreadsRouteScreen.tsx` | The composer shows the desktop's stats line (limits, context, tok/s, cache) with the same detail rows in sheets and a Compact now action, behind Settings > Threads > Stats for nerds (off by default, per device). Web and mobile share the calculations. | Tests in `checks-ios.json`. In the app, with the switch on, a thread shows the stats row under the composer and its sheets match the desktop popovers. |
| iOS child threads (`patches-ios/0004`) | `packages/client-runtime/src/state/{threadFamilies,threadShell}.ts` (web `Sidebar.families.ts` re-exports), `apps/mobile/src/features/threads/{threadListV2.ts,thread-list-v2-items.tsx,ThreadNavigationSidebar.tsx,use-thread-list-v2-shelf-preferences.ts}`, `apps/mobile/src/features/home/{HomeRouteScreen,HomeScreen}.tsx`, `apps/mobile/src/state/entities.ts`, `apps/mobile/src/persistence/mobile-preferences.ts` | The thread list and iPad sidebar nest child threads under their opener with the desktop's rules (`openedByThreadId`, settled children to Settled unless still running, `delegate_task` workers in their delegator's section), guide line, no favicon, "Hide/Show child threads" in the long-press menu and the collapsed stub. Older threads stay flat. Depends on `patches-tt/0003`. | Tests in `checks-ios.json`. In the app, a thread that launched another shows it nested beneath it. |
| iOS direct push (`patches-ios/0005`) | `apps/mobile/app.config.ts`, `apps/mobile/src/connection/{direct-push,runtime}.ts`, `apps/mobile/src/features/agent-awareness/{capabilities,remoteRegistration,directPushSnapshot}.ts`, `apps/mobile/src/features/settings/{SettingsNotificationsRouteScreen,SettingsRouteScreen,DirectPushSettingsNotificationsRouteScreen}.tsx` | A custom-identity build (`extra.directServerPush`) registers its push token, Live Activity token and preferences with every paired server, again whenever a server connects, with no Clerk or relay involved. Settings > Notifications shows a screen with two stock switches. The official build keeps the relay path. Depends on `patches-tt/0004`. | Tests in `checks-ios.json`. In the app, Settings > Notifications shows both switches on once a server with the key has accepted the device. |
| iOS Claude theme (`patches-ios/0006`) | `packages/shared/src/themePalettes.ts`, `apps/mobile/src/lib/{mobileTheme,mobileThemeRuntime}.ts`, `apps/mobile/scripts/generate-uniwind-themes.mts`, `apps/mobile/{generated-uniwind-themes.css,generated-uniwind-theme-names.json,uniwind-types.d.ts}` | The desktops' `claude` environment theme (`~/.t3/userdata/themes/claude.json`) as a mobile palette in Settings > Appearance, light and dark; roles the file omits fall back to T3 Chat as on desktop; `messageAction` is `#ba5b3b` so white button text keeps 4.5:1. Not a web built-in, so desktops can still publish `claude.json`. If `claude.json` changes, update `CLAUDE_THEME`; if upstream mobile starts following environment themes, propose dropping this patch. | Tests in `checks-ios.json`. In the app, Appearance shows a Claude card; selecting it gives a `#151515` canvas in dark and `#fcfcfb` in light with terracotta primary buttons. |
| iOS build | `t3code-customize` (`cmd_ios`, `build_ios`, `ios_app_id`, `ios_testers`), `ios.json` | Builds `apps/mobile` for the nightly commit installed on the Mac with `expo prebuild` and `xcodebuild archive` (automatic signing with the App Store Connect API key), uploads with asc-cli and keeps the internal TestFlight group and its testers. Depends on upstream's `apps/mobile/app.config.ts` version field and Expo prebuild layout. | `./t3code-customize ios` ends with the build on TestFlight; `asccli builds list --app-id <id>` shows it. |
| macOS launcher | `t3code-customize` (`install_mac_launcher`, `cmd_update`, `cmd_autoupdate`) | Upstream's overlay: the signed `T3 Code (Nightly).app` stays untouched (passkeys, keychain, T3's updater work); the launcher in `/Applications/T3 Code (Customized).app` (fork: upstream uses `~/Applications`, which stays the fallback when `/Applications` is not writable) starts it with `--inspect-brk` and loads the build from `~/.local/share/t3code-customize/builds/<build>/overlay`. The fork adds: the launcher removes the re-signed app copy and the launcher earlier versions put in `~/Applications`. `autoupdate on` is a LaunchAgent that watches the app's `Info.plist` and `app.asar` (`WatchPaths`) plus an hourly check; it runs `update --background`, which waits until T3's updater stops writing (`app_settled`), rebuilds and notifies "quit and reopen". A launcher opened on an outdated build opens stock and starts that rebuild (`start_background_update`). When the patches conflict, the notification says to ask an agent in this repo to port them (with `--fix claude` the agent ports unattended and the notification asks to commit and run fleet). | `./t3code-customize status` says the next launch opens the customized build; opening the launcher logs "Opened T3 Code with the customization" in `~/.cache/t3code-customize/logs/launch.log`, and the app shows the stats and child threads. |
| T3 server | `t3code-customize` (`cmd_server`, `build_server`, `install_server_build`, `restart_server`, `server_autoupdate`) | Patched `t3` and `client/` in `~/.t3/runtime/versions/<active>/`, built from tag `v<version>` with `VP_NODE_VERSION` = upstream's `SEA_NODE_VERSION`; originals kept as `*.stock`; health check on port 3773 or back to stock. Depends on upstream's `apps/server/scripts/cli.ts build-exe` and the runtime layout. | `./t3code-customize status` on devbox1 shows "Customized: yes"; `curl` on port 3773 gives 200; `t3 connect status --json` is still linked. |
| Fleet | `t3code-customize` (`cmd_fleet`, `sync_repo`), `machines.json` | One command updates every machine from any machine; files arrive by Syncthing or SSH copy, identical script and recipe hash required before building. | `./t3code-customize fleet` ends with every machine `ok`. |
| Hermetic checks | `t3code-customize` (`checks`) | Tests and typechecks run with `HOME` set to an empty temp dir, as in upstream's CI, and `TMPDIR` under `~/.cache/t3code-customize/tmp` (devbox1's `/tmp` is a tmpfs with a user quota that filled up mid-test, `EDQUOT`). Upstream's ClaudeAdapterV2 steer test "(never answers)" reads the real `~/.claude/skills` mid-steer and hangs once there are many skills (devbox1, 73). Upstream's `vp lint` also runs on every file the patches add or change: its `no-hermes-unsupported-apis` rule catches APIs Hermes lacks (`Array#toSorted` crashed the iOS composer stats), which tests on Node and typechecks miss. | `./t3code-customize build --resume` passes the checks on devbox1. |
| Checkout guard | `t3code-customize` (`prepare`, `main`) | A fresh build stops instead of aborting a stopped rebase or `git am` or discarding uncommitted edits in the source checkout, since they may be a port in progress; the lock file `~/.cache/t3code-customize/lock` names the run that holds it, and a second run says so. | With a tracked edit in the checkout, `prepare` stops and the edit survives; with the lock held, a second run prints the holder. |
| Upstream merge | `t3code-customize` (`pull_latest`) | Each run merges `upstream/main` when it merges cleanly, else continues with the patches it has. | `git log upstream/main..HEAD` shows only fork commits after a run. |

## Agent skills

### Issue tracker

GitHub Issues on the fork `timvdhoorn/t3code-customize-tt`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created when needed. See `docs/agents/domain.md`.
