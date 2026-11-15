# Current port

> Source: `patches-port/base.txt`, `covered-nightly.txt`, `skip-shared.json`; `./t3code-customize status`
> Updated: 2026-11-15

Which nightly the patches cover and what a port of them has to watch for. The port loop itself is in [docs/porting.md](../../docs/porting.md).

## Coverage
- Shared patches: `patches-port/` targets nightly 0.1.10-nightly.20261115.4749 (`295a0a7332aa`).
- `patches/` is upstream's and stays untouched.
- Own patches: `patches-tt/` (14) and `patches-ios/` (9); a port applies 2 shared commits (`patches-port/`, minus the skips) + 14 + 9 = 25 commits.
- `covered-nightly.txt`: 0.1.10-nightly.20261115.4749.
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
