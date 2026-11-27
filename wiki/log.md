# Log

One line per change, newest first. Format: [RULES.md](RULES.md#formats).

- 2026-11-27 change | Own signed macOS app for nightlies without the inspector fuse; MacBook Pro runs signed 5332 (PR open, issue #152) | machines/macs.md | docs/fork-changes.md
- 2026-11-27 change | Cmd+L cites the assistant selection: new own patch `patches-tt/0017`, command `chat.citeSelection` (PR open) | - | docs/fork-changes.md, checks-tt.json
- 2026-11-27 change | Patches ported to nightly 0.1.14-nightly.20261127.5332 (shared tooltip #42671, configurable mobile fonts #43840) | porting/current-port.md | docs/fork-changes.md
- 2026-11-26 change | Patches ported to nightly 0.1.13-nightly.20261125.5258; one conflict, the terminal canvas fill in `patches-tt/0007` (PR open) | porting/current-port.md | patches-tt/
- 2026-11-26 fix | A listed known upstream failure stays tolerated after a pass (flaky test broke the MacBook Pro iOS build of 2026-11-25); `status` advises on removal (PR open) | - | docs/machines.md
- 2026-11-25 remove | Unused web re-export `Sidebar.families.ts` out of `patches-tt/0002`; nothing imported it: patch lines 9962 → 9951 (PR open) | - | docs/fork-changes.md
- 2026-11-25 remove | Duplicate web test `Sidebar.families.test.ts` out of `patches-tt/0002`; its 36 tests run in `childThreadFamilies.test.ts`: patch lines 10489 → 9962 (PR open) | - | docs/fork-changes.md
- 2026-11-25 change | Own code moved from 5 upstream files to patch-owned ones (list in `docs/fork-changes.md`): upstream production lines 7031 → 6559 (PR open) | - | docs/porting.md
- 2026-11-25 change | Own tests moved from upstream test files to 17 patch-owned ones (in `checks-tt.json`/`checks-ios.json`): upstream test lines 2581 → 1310 (PR open) | - | docs/porting.md
- 2026-11-25 change | `patches-tt/0002` creates the family rules (`childThreadFamilies.ts`, test in `checks-tt.json`) in client-runtime; `patches-ios/0004` no longer moves them (PR open) | - | docs/fork-changes.md
- 2026-11-25 add | Settle a finished or failed agent from the sidebar chips popover and the iOS chips menu (`patches-tt/0002`, `patches-ios/0004`, PR open) | porting/current-port.md | docs/fork-changes.md
- 2026-11-25 fix | Sidebar hover-delay test no longer flakes on the Macs: vitest-browser ran the fake clock during a slow hover; the test holds it (`patches-tt/0002`, PR open) | porting/current-port.md | checks
- 2026-11-25 change | Own patches no longer rewrap upstream lines: `patches-tt/0006` 522 → 418 changed upstream lines, 4 others touched; rule and check in porting.md (PR open) | porting/current-port.md | docs/porting.md
- 2026-11-25 remove | `patches-tt/` 18 → 16: branch-off-meta-line and picker/effort bar/row timer patches dropped, rest renumbered (PR open) | porting/current-port.md | docs/fork-changes.md
- 2026-11-25 change | Patches ported to nightly 5230: thread menu (readMenu), triage queue, iOS canSwipe; Air update race filed as #134 | porting/current-port.md | checks
- 2026-11-24 change | Patches ported to nightly 5204: 4 conflicts, 2 check fixes (settlement field rename, subagent-of label test) (PR open) | porting/current-port.md | checks
- 2026-11-23 change | Patches ported to nightly 5138: 3 own-patch conflicts (workflowRun fields, workflow RPCs, divider paren in tt/0006) (PR open) | porting/current-port.md | checks
- 2026-11-23 fix | Compaction replay ignored (`patches-tt/0016`): live-compact plugin no longer moves old tool items into the running turn (PR open) | status.md | docs/fork-changes.md
- 2026-11-22 fix | Port to 5098; pushes after 5+ idle min were lost (31%): APNs reconnect + resend, Done instant, child threads silent (PR open) | porting/current-port.md | docs/fork-changes.md
- 2026-11-22 dream | Pages replayed against status, units, patch counts, ios.json, TestFlight keys; no value differed, no duplicates; sessions since 11-15 held no new durable facts | index.md | lint
- 2026-11-22 change | MBP on 5085; iOS build 202611221444 with the quiet-list fix on TestFlight | status.md | t3code-customize status
- 2026-11-22 change | MBP on 5009; iOS build 202611221342 uploaded to TestFlight (agreement blocker gone) | status.md | t3code-customize status
- 2026-11-22 fix | Quiet thread list built from the shell index (`patches-tt/0015`): iOS cold start no longer blocks 30 s | status.md | docs/fork-changes.md
- 2026-11-20 change | Patches ported to nightly 5009: all patch copy translated for upstream i18n (#37893) (PR open) | porting/current-port.md | patches-tt/, patches-ios/
- 2026-11-16 change | Claude context categories in thread details and the iOS context sheet, `patches-tt/0014` + `patches-ios/0011` (PR open) | status.md | docs/fork-changes.md
- 2026-11-15 change | Patches ported to nightly 4749 incl. patches-ios (swipe-actions conflict) | porting/current-port.md | patches-ios/
- 2026-11-15 change | Host load (CPU cores and threads, memory, storage) in thread details, core breakdown toggle (PR open) | status.md | docs/fork-changes.md, patches-tt/0013
- 2026-11-15 change | One-column model picker, segmented effort bar and live row timer as a `patches-tt/` patch, dropped 2026-11-25 (PR open) | status.md | docs/fork-changes.md
- 2026-11-15 change | Patches ported to nightly 4736; Open button now in Background work details | porting/current-port.md | patches-tt/
- 2026-11-15 change | Worker popover opens on hover and shows each agent's model (PR open) | status.md | docs/fork-changes.md
- 2026-11-14 fix | Manual port --resume opens no PR: docs corrected | porting/current-port.md | docs/porting.md
- 2026-11-14 setup | Knowledge base created: machines, porting, status | index.md | AGENTS.md, docs/
