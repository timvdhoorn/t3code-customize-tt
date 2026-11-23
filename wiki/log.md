# Log

One line per change, newest first. Format: [RULES.md](RULES.md#formats).

- 2026-11-23 change | Patches ported to nightly 5138: 3 own-patch conflicts (workflowRun fields, workflow RPCs, divider paren in tt/0006) (PR open) | porting/current-port.md | checks
- 2026-11-23 fix | Compaction replay ignored (`patches-tt/0018`): live-compact plugin no longer moves old tool items into the running turn (PR open) | status.md | docs/fork-changes.md
- 2026-11-22 fix | Port to 5098; pushes after 5+ idle min were lost (31%): APNs reconnect + resend, Done instant, child threads silent (PR open) | porting/current-port.md | docs/fork-changes.md
- 2026-11-22 dream | Pages replayed against status, units, patch counts, ios.json, TestFlight keys; no value differed, no duplicates; sessions since 11-15 held no new durable facts | index.md | lint
- 2026-11-22 change | MBP on 5085; iOS build 202611221444 with the quiet-list fix on TestFlight | status.md | t3code-customize status
- 2026-11-22 change | MBP on 5009; iOS build 202611221342 uploaded to TestFlight (agreement blocker gone) | status.md | t3code-customize status
- 2026-11-22 fix | Quiet thread list built from the shell index (`patches-tt/0017`): iOS cold start no longer blocks 30 s | status.md | docs/fork-changes.md
- 2026-11-20 change | Patches ported to nightly 5009: all patch copy translated for upstream i18n (#37893) (PR open) | porting/current-port.md | patches-tt/, patches-ios/
- 2026-11-16 change | Claude context categories in thread details and the iOS context sheet, `patches-tt/0016` + `patches-ios/0011` (PR open) | status.md | docs/fork-changes.md
- 2026-11-15 change | Patches ported to nightly 4749 incl. patches-ios (swipe-actions conflict) | porting/current-port.md | patches-ios/
- 2026-11-15 change | Host load (CPU cores and threads, memory, storage) in thread details, core breakdown toggle (PR open) | status.md | docs/fork-changes.md, patches-tt/0014
- 2026-11-15 change | One-column model picker, segmented effort bar and live row timer as `patches-tt/0015` (PR open) | status.md | docs/fork-changes.md
- 2026-11-15 change | Patches ported to nightly 4736; Open button now in Background work details | porting/current-port.md | patches-tt/
- 2026-11-15 change | Worker popover opens on hover and shows each agent's model (PR open) | status.md | docs/fork-changes.md
- 2026-11-14 fix | Manual port --resume opens no PR: docs corrected | porting/current-port.md | docs/porting.md
- 2026-11-14 setup | Knowledge base created: machines, porting, status | index.md | AGENTS.md, docs/
