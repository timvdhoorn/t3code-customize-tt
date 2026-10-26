# Porting the patches to a new T3 Code nightly

These instructions are for a coding agent. A person can follow them too.

The patches in `patches/` are commits made against the upstream commit in
`patches/base.txt`. Upstream moves fast, so they often stop applying cleanly. Your job
is to carry them onto the user's nightly with every feature still working.

## Start

Every update or port of this fork also runs the upstream check in "Checking an update" in
[docs/fork-changes.md](docs/fork-changes.md#checking-an-update), step 2, for each row that ports an
upstream PR or works around an upstream issue; `status`, `build`, `update` and `server` print the
PRs in `ported-prs.json`. In this fork a port runs through `port`, `continue` and `checks`:
[docs/porting.md](docs/porting.md).

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

Fork: the porting loop (`continue`, `checks`, `port`) is in [docs/porting.md](docs/porting.md); `build --resume` claims the stopped checkout, so no unattended run cleans it up.

End with a short report: what changed upstream, what you changed and in which files,
and whether the final build succeeded. Separate fixture tests, native process
checks and real desktop startup evidence.

## Fork changes

This repo is Tim's fork of [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize).
Every update must carry the fork's own changes forward, and an agent must confirm that
upstream did not break or duplicate them.

**This repo is public.** Never commit secrets or private data: no keys, tokens, passwords,
`.p8` or `.bin` contents, pairing URLs, Tailscale IPs, customer names or log excerpts with
personal data. Name where a secret lives (a 1Password item, a path under
`~/.t3/userdata/secrets/`) instead of its value, and check the staged diff before every commit.

### Ownership

| Upstream owns (never commit changes) | The fork owns (commit changes) |
| --- | --- |
| `patches/*.patch`, `patches/base.txt`, `checks.json` | `patches-port/`, `patches-tt/`, `checks-tt.json`, `patches-ios/`, `checks-ios.json`, `ios.json`, `ported-prs.json`, `.agents/playbooks/`, this section, `docs/fork-changes.md`, `docs/machines.md`, `docs/porting.md`, `CLAUDE.md` |
| the Linux, Windows and macOS build and launch paths in `t3code-customize`, `platform_support.py`, `macos/`, `install.ps1`, `tests/`, `docs/macos.md` | update, autoupdate, server, fleet and ios code in `t3code-customize`, `machines.json`, `tests/test_checkout_guard.py`, `tests/test_unattended_updates.py`, `tests/test_port_flow.py`, `tests/test_lint_step.py`, `tests/test_typechecker.py`, `tests/test_ios_build.py`, the `README.md` macOS, server and machines sections |

- A port of the shared patches goes to `patches-port/` (with its own `base.txt`), never to
  `patches/`; the tool writes it there. Builds use it while it targets a newer nightly than
  `patches/base.txt`. Once upstream catches up, the tool says `patches-port/` is unused:
  delete it in a commit.
- Every change to T3 Code itself is one commit in `patches-tt/`, with its tests in
  `checks-tt.json` and a row in [docs/fork-changes.md](docs/fork-changes.md). Never fold it into a shared patch.
- A change only the iOS app needs is one commit in `patches-ios/`, with its tests in
  `checks-ios.json` and a row in [docs/fork-changes.md](docs/fork-changes.md). Only `t3code-customize ios` applies this folder, after
  `patches-tt/`, so the desktop app and the servers never carry it. Moving shared code for iOS
  (into `packages/client-runtime`, say) keeps the old module as a re-export and the old test
  files in place, because `checks-tt.json` still names them.


### Where the rest lives

- **Porting** (a conflict, a failing check, `--fix`, `port`, `continue`, `checks`, changing a patch
  by hand): [docs/porting.md](docs/porting.md).
- **A fork change** (what each own patch and each tool addition must keep doing, its files and its
  check; the check after every update): [docs/fork-changes.md](docs/fork-changes.md). A new own patch
  or tool behaviour adds its row there.
- **Machines** (which machine updates how, the porter, the idle gate that never interrupts a running
  thread, the standing grant for unattended ports, `fleet` after every pushed change):
  [docs/machines.md](docs/machines.md).
- **Asked to update** ("update", "zijn er updates", "update alles"):
  [.agents/playbooks/update.md](.agents/playbooks/update.md).
- After every change to this repo that is committed and pushed, run `./t3code-customize fleet` and
  report the summary per machine ([docs/machines.md](docs/machines.md); from a T3 agent it detaches, so read it from its journal in a later turn).
- Python stays compatible with macOS's system Python 3.9. Before reporting a change to the script:
  `python3 -m py_compile t3code-customize`, `python3 -m unittest discover -s tests` and
  `./t3code-customize status`.
- When upstream changes `t3code-customize`, merge it by hand if `pull_latest` could not: keep the
  `update`, `autoupdate`, `server`, `fleet`, `port`, `continue`, `checks`, `ios` and own-patch code,
  the lock that names its holder and Python 3.9 compatibility, then run the checks above.

## Agent skills

### Issue tracker

GitHub Issues on the fork `timvdhoorn/t3code-customize-tt`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created when needed. See `docs/agents/domain.md`.
