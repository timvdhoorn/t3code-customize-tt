# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-15

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.10-nightly.20261115.4749 on `main`; see [Current port](porting/current-port.md).
- Server build checks the `skip-shared.json` markers (`9a590e0`); see [devbox1](machines/devbox1.md).
- MacBook Air: 4682 with the patches.

## In progress
- devbox1: the 4682 build with patches is staged; the restart waits until no thread works.
- Build the Mac overlay before install-on-quit, so the first launch after an update opens the customized build (worker PR, not opened yet); see [Macs](machines/macs.md).
- Worker popover on hover with a model line per agent (`patches-tt/0002`): PR open, not merged; see [docs/fork-changes.md](../docs/fork-changes.md).
- Host load in thread details with a core breakdown toggle (`patches-tt/0014`): PR open, not merged; drop when pingdotgg/t3code#36693 merges; see [docs/fork-changes.md](../docs/fork-changes.md).
- One-column picker, effort bar and row timer (`patches-tt/0015`, desktop and web): PR open, not merged; replaces the Macs' `claude` theme CSS once live; see [docs/fork-changes.md](../docs/fork-changes.md).

## Open
- MacBook Pro: 4580 with patches; installs 4682 when T3 Code quits.
- TestFlight: blocked on an App Store Connect agreement only the Account Holder can accept; see [TestFlight](machines/testflight.md).
