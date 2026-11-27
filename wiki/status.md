# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-27

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.14-nightly.20261127.5332 on `main` (PR #150); see [Current port](porting/current-port.md).
- devbox1: server runs 5332 with the patches. See [devbox1](machines/devbox1.md).
- MacBook Pro: own signed T3 Code 5345 (PR #158), installed 2026-11-27; T3's 5258 app in
  `~/.local/share/t3code-customize/rollback/`. TestFlight: T3 Code TT 2.4.0 (202611272015) for 5345.

## In progress
- MacBook Pro: a newly signed app blocks on the keychain prompt for "t3code Safe Storage" until Tim
  answers it with Always Allow; until then the UI hangs. `fleet` after PR #158 turns the update
  LaunchAgent on again.
- MacBook Air: offline (with Tim); stays on 5258 until it has a "Developer ID Application" identity
  in its login keychain (export it from the MacBook Pro as .p12, 1Password).

## Open
- Macs: the own signed app has no passkeys (Tim accepts this, 2026-11-27); watch upstream
  t3code-customize for a new macOS hook.
