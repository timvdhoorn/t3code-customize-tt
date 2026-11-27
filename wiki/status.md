# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-27

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.14-nightly.20261127.5332 on `main` (PR #150); see [Current port](porting/current-port.md).
- devbox1: server runs 5332 with the patches. See [devbox1](machines/devbox1.md).

- MacBook Pro: own signed T3 Code 5332 (issue #152 branch `t3/macos-customized-signed-updates`, PR open), installed 2026-11-27; T3's 5258 app in `~/.local/share/t3code-customize/rollback/`.

## In progress
- Own signed macOS app (issue #152): PR from `t3/macos-customized-signed-updates`, not merged. Until
  it merges, the MacBook Pro's `com.github.t3code-customize.update` LaunchAgent is booted out (main's
  code cannot update the signed app); `fleet` after the merge turns it on again.
- MacBook Air: offline (with Tim); stays on 5258 until it has a "Developer ID Application" identity
  in its login keychain (export it from the MacBook Pro as .p12, 1Password).

## Open
- Macs: the own signed app has no passkeys (Tim accepts this, 2026-11-27); watch upstream
  t3code-customize for a new macOS hook.
