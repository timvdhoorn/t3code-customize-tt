# Current port

> Source: `patches-port/base.txt`, `covered-nightly.txt`, `skip-shared.json`; `./t3code-customize status`
> Updated: 2026-11-14

Which nightly the patches cover and what a port of them has to watch for. The port loop itself is in [docs/porting.md](../../docs/porting.md).

## Coverage
- Shared patches: `patches-port/` targets nightly 0.1.10-nightly.20261114.4682 (`820f620e3d63`).
- `patches/` is upstream's and stays untouched.
- Own patches: `patches-tt/` (12) and `patches-ios/` (9); a port applies 2 shared commits (`patches-port/`, minus the skips) + 12 + 9 = 23 commits.
- `covered-nightly.txt`: 0.1.10-nightly.20261114.4682.
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
- Upstream PRs named in `docs/fork-changes.md`: #16699 is open, so the child-threads patch stays.
