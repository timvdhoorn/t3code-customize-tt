# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-20

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.11-nightly.20261117.4851 on `main`; see [Current port](porting/current-port.md).
- MacBook Pro: 4851 with the patches; the iOS build is for 4851.

## In progress
- Port to nightly 0.1.12-nightly.20261120.5009 (i18n rewrite): PR open, not merged.
- devbox1: server runs 4969 without the patches; the 04:30 unattended run hit a conflict and left a rebase in the shared checkout; the 5009 port replaces it. See [devbox1](machines/devbox1.md).
- MacBook Air: 4761 with the patches; 4851 is staged and installs when T3 Code quits.

## Open
- TestFlight: blocked on an App Store Connect agreement only the Account Holder can accept; see [TestFlight](machines/testflight.md).
