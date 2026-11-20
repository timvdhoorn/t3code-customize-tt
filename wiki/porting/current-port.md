# Current port

> Source: `patches-port/base.txt`, `covered-nightly.txt`, `skip-shared.json`; `./t3code-customize status`
> Updated: 2026-11-20

Which nightly the patches cover and what a port of them has to watch for. The port loop itself is in [docs/porting.md](../../docs/porting.md).

## Coverage
- Shared patches: `patches-port/` targets nightly 0.1.12-nightly.20261120.5009 (`f0a2aa10f516`).
- `patches/` is upstream's and stays untouched.
- Own patches: `patches-tt/` (16) and `patches-ios/` (11); a port applies 2 shared commits (`patches-port/`, minus the skips) + 16 + 11 = 29 commits.
- `covered-nightly.txt`: 0.1.12-nightly.20261120.5009.
- Left out (`skip-shared.json`): desktop stats line and throughput, compaction settings, subscription switch.
- Their bundle markers are replaced by `markers` in the same file.

## Gotchas
- `git-guard` blocks `git add -A`/`git add .`, also inside a port worktree; stage each resolved file by name.
- A blocked command runs nothing at all: check for conflict markers (`rg -n '^(<<<<<<<|>>>>>>>) '`) before `continue`.
- `git checkout --merge <file>` re-creates a conflict; a misaligned conflict in a test file is easiest to resolve from the nightly's file plus the patch's added hunks, then compare the `+`/`-` lines with the patch.
- `checks` runs the desktop/server stack (`HEAD~<ios count>`) first; a failure there is fixed in the shared or `patches-tt/` commit, never in `patches-ios/`.
- `port --resume --dry-run` saying the patches do not keep the same code lines means the PR waits for review; expected whenever conflicts changed code.
- `port --resume` writes the patch folders and `covered-nightly.txt` here but opens no PR.
- Commit them as `chore: port patches to nightly <version>` on a branch and open the PR yourself.
- 4749 conflict: upstream sized the swipe actions from the measured row (`compactActions`, `rowHeight`, label constants) in `thread-swipe-actions.tsx`; `patches-ios/0004` keeps both and adds `iconOnlyActions`.
- Upstream PRs named in `docs/fork-changes.md`: #16699 is open, so the child-threads patch stays.
- 4838: upstream dropped `resolveSidebarRowThreadId`; `patches-tt/0002` keeps `resolveSidebarRowThreadKey`, iOS keeps `resolveThreadListV2RowKey` over upstream's `useSidebarRowThreadKey`.
- 4838: upstream refreshes the update check before a download (#37476, `downloadAvailableUpdate(refresh)`); the automatic covered download in `patches-tt/0005` passes `false` so it never fetches an uncovered nightly.
- 5009: upstream translated the app with gt-react (#37893); the `no-untranslated-copy` lint in `checks` fails on bare copy.
- Patch copy goes through `msg()` (resolved with `m`/a `MessageResolver`), `useGT()` (`gt("…")`) or `<T>`/`<Var>`. Call `useGT()` before an early return.
- A web unit test rendering a `useGT` component needs `initializeGT` from `gt-react` plus `<GTProvider locale="en">`.
- `initializeGTSPA` throws under Node; see `V2LifecycleRow.kind.test.tsx`.
- 5009: patch strings are not in the GT catalogs, so other locales show English; upstream's `i18n:check` is not part of our checks.
- 5009: `ProviderHost` needs `compatibility` (`noCompatibilityPolicy` in test fixtures); Codex reads `config/read` before `thread/start`.
