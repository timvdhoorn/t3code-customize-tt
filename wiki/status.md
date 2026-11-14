# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-14

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.10-nightly.20261114.4682 on `main` (#107); see [Current port](porting/current-port.md).
- Server build checks the `skip-shared.json` markers (`9a590e0`); see [devbox1](machines/devbox1.md).
- MacBook Air: 4682 with the patches.

## In progress
- devbox1: the 4682 build with patches is staged; the restart waits until no thread works.
- Build the Mac overlay before install-on-quit, so the first launch after an update opens the customized build (worker PR, not opened yet); see [Macs](machines/macs.md).

## Open
- MacBook Pro: 4580 with patches; installs 4682 when T3 Code quits.
- TestFlight: blocked on an App Store Connect agreement only the Account Holder can accept; see [TestFlight](machines/testflight.md).
