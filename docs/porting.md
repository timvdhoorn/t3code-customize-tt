# Porting the patches

For an agent that carries the patches onto a new T3 Code nightly. A port is done when
`./t3code-customize continue` says "All patches applied." and `./t3code-customize checks`
passes, with one commit per patch and every feature in [fork-changes.md](fork-changes.md)
still doing what its row says.

## The layers

A port applies three layers on top of the nightly commit, in order:

1. the shared patches (`patches-port/` while it targets a newer nightly than `patches/base.txt`,
   else `patches/`), rebased from their base onto the nightly;
2. `patches-tt/`, with `git am --3way`;
3. `patches-ios/`, with `git am --3way` (only `port` and `ios` apply it; a desktop `build` and
   `server` stop after `patches-tt/`).

Each layer that conflicts stops the run with the conflicted files and the stage it is in.

## The loop

Run every command from the repo (`./t3code-customize`, or the path the prompt gives). Pass
`--source <dir>` when you work in your own worktree instead of the shared checkout
`~/.cache/t3code-customize/t3code`; the prompt includes it when the run needs it.

1. **Resolve** each conflicted file, then `git add` it. Keep upstream's change and carry the
   patch's intent onto it; when upstream moved or split a file, carry the change to the new
   location and follow the new APIs. `git log <base>..<nightly>` and `git show` explain what
   upstream changed; the row in [fork-changes.md](fork-changes.md) says what an own patch must
   keep doing.
2. **`./t3code-customize continue`** finishes the stopped stage (`git rebase --continue` or
   `git am --continue`), applies the next layer and prints the next conflict, or
   "All patches applied." Back to step 1 until it says that.
3. **`./t3code-customize checks`** installs dependencies if needed and runs every test, typecheck
   and lint in `checks.json`, `checks-tt.json` and (with `patches-ios/`) `checks-ios.json`. It
   prints `pass` or `FAIL` per step with the failing files; the full output is in the log it names.
   With `patches-ios/` it first runs them on the commit below that layer, the stack the desktop app
   and the servers build, so a fix belongs in the shared or `patches-tt/` commit that needs it.
   A test file that failed only by a timeout runs once more on its own before it counts; a
   non-zero exit with an unhandled error fails the step too. When everything passes it stamps the
   commit (with the nightly, the check lists and the recipe), so the tool's own run afterwards skips
   the checks.
4. **Fix** a failing check in the commit of the patch that causes it: `git commit --fixup=<sha>`,
   then `git -c sequence.editor=true rebase -i --autosquash <nightly commit>`. Run `checks` again.
   If a test file moved upstream, its path in the check list moves with it (say so in your report).

Started by the tool (`--fix`, `port`): stop once `checks` passes. The tool exports the commits to
the patch folders, opens the PR and decides on merging; you do not export, commit to this repo,
push or build.

## The rules of a port

- One commit per patch, in the same order; the export maps commits to patches by count.
- A port keeps every patch and every test. A failing check is fixed in the patch, so the checks
  stay as strong as before and no step is skipped.
- A feature that cannot be ported sensibly: stop and explain why, with the patch and the upstream
  change that blocks it.
- `node_modules` comes from `pnpm install --frozen-lockfile --ignore-scripts`; `checks` runs it.

## By hand, outside a tool run

The shared checkout belongs to whichever run holds `~/.cache/t3code-customize/lock` (the file names
the holder). `continue`, `checks` and `build --resume` claim a stop there, so no unattended run
cleans it up while you work on it.

A run killed during its agent session (reboot, OOM, its unit stopped) never records how it left
the checkout; the marker names that session (the run's pid and start time, and its unit). A later
unattended run aborts such a stop when that run is gone and nobody claimed the checkout. The
tradeoff: a hand edit made there after such a kill, without any tool call, is lost. Run `continue`
or `checks` first; either claims the checkout and protects it. Work in your own detached worktree:

```sh
git -C ~/.cache/t3code-customize/t3code worktree add --detach <dir> HEAD
./t3code-customize port --source <dir> --version <nightly version> --dry-run
```

`port` applies all three layers onto that nightly (the newest when you leave out `--version`),
then you run the loop above with `--source <dir>`, and `port --source <dir> --version <v> --resume
--dry-run` exports the result to `~/.cache/t3code-customize/port-dry-run/<v>/` and says whether
every patch kept its code lines. Without `--dry-run` it writes the patch folders in this repo and
opens the PR (see [machines.md](machines.md#unattended-ports)). Remove the worktree when done
(`git -C ~/.cache/t3code-customize/t3code worktree remove <dir>`).

To change a patch rather than port it, apply the patches in such a worktree, commit the change into
the patch's commit, run `checks --source <dir>`, and regenerate the patch folder as `export_patches`
does (`git format-patch --no-signature --zero-commit`, one file per commit).

## After the port

Check per row of [fork-changes.md](fork-changes.md) that upstream did not break or duplicate it,
as [fork-changes.md](fork-changes.md#checking-an-update) describes, and report per row: unaffected,
ported (what changed), or needs a decision.
